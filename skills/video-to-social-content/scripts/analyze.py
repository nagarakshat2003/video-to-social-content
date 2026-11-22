#!/usr/bin/env python3
"""
analyze.py - Turn the source video into evidence the agent can read quickly.

One ffmpeg decode pass collects scene cuts, loudness, silences and sample
frames; transcription (optional) runs in parallel. Results go to
outputs/<name>/analysis/:

  transcript.json   segments + word timestamps (faster-whisper or openai-whisper;
                    or imported with --subtitles file.srt|.vtt)
  scenes.json       scene-cut times
  loudness.json     momentary loudness per second (LUFS) + integrated loudness
  silences.json     silent stretches (good cut points)
  candidates.json   ranked, sentence-aligned reel windows with reasons
  sheets.json       contact sheets (samples/sheets/sheet_NNN.jpg), each tile's
                    timestamp, and the scale factor from tile to source pixels

Results are cached: re-running skips work whose inputs did not change
(use --force to redo everything).

Usage:
  analyze.py outputs/<name> [--model small] [--language en] [--no-transcribe]
             [--subtitles subs.srt] [--sheet-every SECONDS] [--top 10]
             [--min-length 15] [--max-length 60] [--force]
"""

from __future__ import annotations

import argparse
import html
import math
import re
import shutil
import statistics
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common import ToolError, Workspace, chunks, emit, fail, parse_time, read_json, require, vfr_args, write_json

TILE_COLS, TILE_ROWS = 4, 3
TILE_WIDTH = 320
MAX_SAMPLES = 96
SCENE_THRESHOLD = 0.3
SILENCE_DB = -35
SILENCE_MIN_S = 0.4
LAUGH_RE = re.compile(r"\b(ha(ha)+|lol|laugh(s|ing|ter)?)\b|\[(laughter|laughs|applause)\]", re.I)
WEAK_OPENERS = {"and", "so", "but", "because", "or", "then", "also", "which", "that"}


# --------------------------------------------------------------------------- helpers

def source_key(meta: Dict[str, Any], extra: str = "") -> str:
    src = Path(meta["source"])
    st = src.stat()
    return f"{src}|{st.st_size}|{st.st_mtime_ns}|{extra}"


def cached(path: Path, key: str, force: bool) -> Optional[Dict[str, Any]]:
    if force or not path.is_file():
        return None
    try:
        data = read_json(path)
    except ValueError:
        return None
    return data if data.get("key") == key else None


def sample_interval(duration: float, requested: Optional[float]) -> float:
    if requested:
        return max(0.5, requested)
    return max(1.0, round(duration / MAX_SAMPLES, 1))


# --------------------------------------------------------------------------- ffmpeg pass

def ffmpeg_pass(ffmpeg: str, meta: Dict[str, Any], ws: Workspace, interval: float) -> Dict[str, Any]:
    frames_dir = ws.samples / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    label = "drawtext=text='%{pts\\:hms}':x=4:y=4:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.6"

    def build(with_text: bool) -> List[str]:
        video = (f"[0:v]split[a][b];"
                 f"[a]scale=160:-2,select='gt(scene,{SCENE_THRESHOLD})',showinfo@scene[sc];"
                 f"[b]select='isnan(prev_selected_t)+gte(t-prev_selected_t,{interval})',showinfo@sample,"
                 f"scale={TILE_WIDTH}:-2" + (f",{label}" if with_text else "") + "[fr]")
        graph = video
        if meta.get("has_audio"):
            graph += f";[0:a]ebur128=framelog=info,silencedetect=n={SILENCE_DB}dB:d={SILENCE_MIN_S}[au]"
        cmd = [ffmpeg, "-hide_banner", "-nostats", "-y", "-i", meta["source"], "-filter_complex", graph,
               "-map", "[sc]", "-f", "null", "-",
               "-map", "[fr]", *vfr_args(ffmpeg), "-q:v", "3", str(frames_dir / "frame_%05d.jpg")]
        if meta.get("has_audio"):
            cmd += ["-map", "[au]", "-f", "null", "-"]
        return cmd

    proc = subprocess.run(build(True), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
    if proc.returncode != 0:  # e.g. ffmpeg built without drawtext/fontconfig
        proc = subprocess.run(build(False), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
        if proc.returncode != 0:
            raise ToolError("ffmpeg analysis pass failed:\n" + proc.stderr[-2000:])
    log = proc.stderr

    def times(tag: str) -> List[float]:
        return [round(float(m.group(1)), 3) for m in
                re.finditer(rf"\[showinfo@{tag} @ [^\]]+\] n:\s*\d+ .*?pts_time:\s*([\d.]+)", log)]

    per_second: Dict[int, float] = {}
    for m in re.finditer(r"\bt:\s*([\d.]+)\s+TARGET:\S+ LUFS\s+M:\s*(-?[\d.]+|-inf)", log):
        if m.group(2) == "-inf":
            continue
        sec, value = int(float(m.group(1))), float(m.group(2))
        per_second[sec] = max(per_second.get(sec, -120.0), value)
    integrated = re.search(r"Integrated loudness:\s*\n\s*I:\s*(-?[\d.]+) LUFS", log)

    silences: List[Dict[str, float]] = []
    start = None
    for m in re.finditer(r"silence_(start|end):\s*(-?[\d.]+)", log):
        if m.group(1) == "start":
            start = max(0.0, float(m.group(2)))
        elif start is not None:
            silences.append({"start": round(start, 3), "end": round(float(m.group(2)), 3)})
            start = None
    if start is not None and meta.get("duration"):
        silences.append({"start": round(start, 3), "end": round(meta["duration"], 3)})

    duration = int(math.ceil(meta.get("duration") or 0))
    loudness = [round(per_second.get(s, -120.0), 1) for s in range(duration)] if per_second else []
    return {
        "scenes": times("scene"),
        "samples": times("sample"),
        "frames": sorted(frames_dir.glob("frame_*.jpg")),
        "loudness": loudness,
        "integrated": float(integrated.group(1)) if integrated else None,
        "silences": silences,
    }


def build_sheets(ffmpeg: str, ws: Workspace, frames: List[Path], times: List[float], meta: Dict[str, Any]) -> Dict[str, Any]:
    if ws.sheets.exists():
        shutil.rmtree(ws.sheets)
    ws.sheets.mkdir(parents=True)
    per_sheet = TILE_COLS * TILE_ROWS
    sheets = []
    for n, group in enumerate(chunks(list(zip(frames, times)), per_sheet), start=1):
        out = ws.sheets / f"sheet_{n:03d}.jpg"
        inputs: List[str] = []
        for frame, _ in group:
            inputs += ["-i", str(frame)]
        cells = len(group)
        rows = math.ceil(cells / TILE_COLS)
        graph = "".join(f"[{i}:v]" for i in range(cells))
        if cells > 1:
            layout = "|".join(
                ("0" if i % TILE_COLS == 0 else "+".join(["w0"] * (i % TILE_COLS))) + "_" +
                ("0" if i // TILE_COLS == 0 else "+".join(["h0"] * (i // TILE_COLS)))
                for i in range(cells))
            graph += f"xstack=inputs={cells}:layout={layout}:fill=black[out]"
        else:
            graph += "null[out]"

        def tile(g: str) -> subprocess.CompletedProcess:
            return subprocess.run([ffmpeg, "-v", "error", "-y", *inputs, "-filter_complex", g, "-map", "[out]",
                                   "-frames:v", "1", "-q:v", "3", str(out)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")

        proc = tile(graph)
        if proc.returncode != 0 and ":fill=black" in graph:  # xstack 'fill' needs a newer ffmpeg
            proc = tile(graph.replace(":fill=black", ""))
        if proc.returncode != 0:
            raise ToolError(f"Could not build contact sheet {out.name}:\n{proc.stderr[-1000:]}")
        sheets.append({
            "file": str(out),
            "start": group[0][1], "end": group[-1][1],
            "grid": f"{TILE_COLS}x{rows}",
            "tiles": [{"index": i, "row": i // TILE_COLS, "col": i % TILE_COLS, "t": t, "frame": str(f)}
                      for i, (f, t) in enumerate(group)],
        })
    return {
        "tile_width": TILE_WIDTH,
        "scale": round(meta["width"] / TILE_WIDTH, 4),
        "note": "Tiles are read left-to-right, top-to-bottom. Multiply tile pixel x/y by 'scale' to get source "
                "display pixels for subject_x/subject_y. Individual frames are in samples/frames/.",
        "sheets": sheets,
    }


# --------------------------------------------------------------------------- transcript

def transcribe(meta: Dict[str, Any], model_name: str, language: Optional[str]) -> Dict[str, Any]:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        WhisperModel = None
    if WhisperModel is not None:
        model = WhisperModel(model_name, device="auto", compute_type="auto")
        segments, info = model.transcribe(meta["source"], language=language, word_timestamps=True, vad_filter=True)
        out = []
        for s in segments:
            out.append({
                "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
                "words": [{"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word.strip(),
                           "prob": round(w.probability, 3)} for w in (s.words or [])],
            })
        return {"engine": "faster-whisper", "model": model_name, "language": info.language, "segments": out}
    try:
        import whisper  # type: ignore
    except ImportError:
        return {"engine": None, "skipped": "No Whisper installed (pip install faster-whisper).", "segments": []}
    model = whisper.load_model(model_name)
    result = model.transcribe(meta["source"], language=language, word_timestamps=True)
    out = [{
        "start": round(s["start"], 3), "end": round(s["end"], 3), "text": s["text"].strip(),
        "words": [{"start": round(w["start"], 3), "end": round(w["end"], 3), "word": w["word"].strip(),
                   "prob": round(w.get("probability", 0), 3)} for w in s.get("words", [])],
    } for s in result.get("segments", [])]
    return {"engine": "openai-whisper", "model": model_name, "language": result.get("language"), "segments": out}


def import_subtitles(path: Path) -> Dict[str, Any]:
    """Parse .srt or .vtt into transcript segments (no word timestamps)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    cue_re = re.compile(r"(\d+:\d{2}(?::\d{2})?[.,]\d{3})\s*-->\s*(\d+:\d{2}(?::\d{2})?[.,]\d{3})[^\n]*\n(.*?)(?:\n\s*\n|\Z)", re.S)
    segments: List[Dict[str, Any]] = []
    prev_raw = ""
    for m in cue_re.finditer(text):
        raw = re.sub(r"<[^>]+>", "", m.group(3))
        raw = html.unescape(" ".join(line.strip() for line in raw.splitlines() if line.strip()))
        if not raw:
            continue
        start, end = (parse_time(m.group(i).replace(",", ".")) for i in (1, 2))
        body = raw
        if segments and prev_raw and raw.startswith(prev_raw):  # rolling auto-captions repeat the previous cue
            body = raw[len(prev_raw):].strip()
        prev_raw = raw
        if not body:
            segments[-1]["end"] = round(end, 3)
            continue
        segments.append({"start": round(start, 3), "end": round(end, 3), "text": body, "words": []})
    return {"engine": "subtitles", "model": None, "language": None, "file": str(path), "segments": segments}


# --------------------------------------------------------------------------- candidates

def _overlap(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    return inter / max(1e-6, min(a[1] - a[0], b[1] - b[0]))


def _units(duration: float, segments: List[Dict[str, Any]], silences: List[Dict[str, float]],
           scenes: List[float]) -> List[Tuple[float, float, str]]:
    """Atomic chunks a reel may start/end on: transcript sentences, else gaps between silences/scenes."""
    if segments:
        return [(s["start"], s["end"], s["text"]) for s in segments]
    cuts = {0.0, round(duration, 3)}
    cuts.update(round((s["start"] + s["end"]) / 2, 3) for s in silences)
    cuts.update(scenes)
    points = sorted(c for c in cuts if 0 <= c <= duration)
    if len(points) <= 2:  # no structure at all: fixed 5 s steps
        points = [round(min(duration, i * 5.0), 3) for i in range(int(duration // 5) + 2)]
        points = sorted(set(points))
    return [(a, b, "") for a, b in zip(points, points[1:]) if b - a > 0.2]


def candidates(duration: float, transcript: Dict[str, Any], loudness: List[float], scenes: List[float],
               silences: List[Dict[str, float]], top: int, min_len: float, max_len: float) -> List[Dict[str, Any]]:
    segments = transcript.get("segments") or []
    units = _units(duration, segments, silences, scenes)
    if not units:
        return []
    if duration < min_len:
        min_len = max(1.0, duration * 0.8)
    loud_vals = [v for v in loudness if v > -70]
    loud_median = statistics.median(loud_vals) if loud_vals else None

    windows = []
    for i in range(len(units)):
        for j in range(i, len(units)):
            start, end = units[i][0], units[j][1]
            length = end - start
            if length > max_len:
                break
            if length < min_len:
                continue
            text = " ".join(u[2] for u in units[i:j + 1]).strip()
            reasons, score = [], 0.0
            if segments:
                words = len(text.split())
                wps = words / length
                score += min(wps, 3.5) / 3.5
                if wps > 2.2:
                    reasons.append(f"dense speech ({wps:.1f} words/s)")
                emphasis = text.count("?") + text.count("!")
                if emphasis:
                    score += min(emphasis, 4) * 0.25
                    reasons.append(f"{emphasis} question/exclamation(s)")
                if LAUGH_RE.search(text):
                    score += 0.6
                    reasons.append("laughter/humor cue")
                first = units[i][2].strip()
                opener = re.sub(r"[^a-z]", "", first.split()[0].lower()) if first.split() else ""
                if first.endswith(("?", "!")) or len(first.split()) <= 8:
                    score += 0.4
                    reasons.append("punchy opening line")
                if opener in WEAK_OPENERS:
                    score -= 0.5
                    reasons.append(f"starts with '{opener}' (may need prior context)")
            if loud_median is not None:
                window_loud = [v for v in loudness[int(start):int(math.ceil(end))] if v > -70]
                if window_loud:
                    lift = statistics.mean(window_loud) - loud_median
                    peak = max(window_loud) - loud_median
                    score += max(-0.5, min(lift, 6)) / 6 + max(0.0, min(peak, 10)) / 20
                    if lift > 2:
                        reasons.append(f"louder than typical (+{lift:.1f} LU)")
            cuts = [t for t in scenes if start < t < end]
            if cuts:
                rate = len(cuts) / length * 10
                score += min(rate, 3) / 6
                if rate >= 1:
                    reasons.append(f"{len(cuts)} scene cut(s)")
            # Prefer lengths near the middle of the recommended range.
            score -= abs(length - (min_len + max_len) / 2) / (max_len * 4)
            windows.append({"start": round(start, 3), "end": round(end, 3), "length": round(length, 2),
                            "score": round(score, 3), "reasons": reasons,
                            "text": (text[:280] + " …") if len(text) > 280 else text})

    windows.sort(key=lambda w: w["score"], reverse=True)
    chosen: List[Dict[str, Any]] = []
    for w in windows:
        if all(_overlap((w["start"], w["end"]), (c["start"], c["end"])) < 0.3 for c in chosen):
            chosen.append(w)
        if len(chosen) >= top:
            break
    for rank, w in enumerate(chosen, start=1):
        w["rank"] = rank
    return chosen


# --------------------------------------------------------------------------- main

def analyze(workspace: Path, model: str = "small", language: Optional[str] = None, transcribe_audio: bool = True,
            subtitles: Optional[Path] = None, sheet_every: Optional[float] = None, top: int = 10,
            min_len: float = 15.0, max_len: float = 60.0, force: bool = False) -> Dict[str, Any]:
    ws = Workspace(workspace)
    if not ws.meta.is_file():
        raise ToolError(f"{ws.meta} not found; run prepare.py first")
    meta = read_json(ws.meta)
    ffmpeg = require("ffmpeg")
    ws.analysis.mkdir(parents=True, exist_ok=True)
    duration = float(meta.get("duration") or 0)
    interval = sample_interval(duration, sheet_every)
    notes: List[str] = []

    # Transcript (in a thread, overlapping the ffmpeg pass).
    t_path = ws.analysis / "transcript.json"
    if subtitles:
        t_key = source_key(meta, f"subs:{Path(subtitles).resolve()}:{Path(subtitles).stat().st_mtime_ns}")
    else:
        t_key = source_key(meta, f"{model}:{language}")
    transcript = cached(t_path, t_key, force)
    t_result: Dict[str, Any] = {}

    def run_transcript() -> None:
        try:
            if subtitles:
                t_result["data"] = import_subtitles(Path(subtitles))
            elif not transcribe_audio:
                t_result["data"] = {"engine": None, "skipped": "disabled with --no-transcribe", "segments": []}
            elif not meta.get("has_audio"):
                t_result["data"] = {"engine": None, "skipped": "source has no audio", "segments": []}
            else:
                t_result["data"] = transcribe(meta, model, language)
        except Exception as exc:  # keep the rest of the analysis useful
            t_result["data"] = {"engine": None, "skipped": f"transcription failed: {exc}", "segments": []}

    worker = None
    if transcript is None:
        worker = threading.Thread(target=run_transcript, daemon=True)
        worker.start()

    # Single decode pass for scenes, loudness, silences and sample frames.
    p_key = source_key(meta, f"pass:{interval}")
    pass_cache = cached(ws.analysis / "scenes.json", p_key, force)
    if pass_cache is None or not (ws.root / "samples" / "sheets").is_dir():
        result = ffmpeg_pass(ffmpeg, meta, ws, interval)
        write_json(ws.analysis / "scenes.json", {"key": p_key, "threshold": SCENE_THRESHOLD, "cuts": result["scenes"]})
        write_json(ws.analysis / "loudness.json", {"key": p_key, "integrated_lufs": result["integrated"],
                                                   "momentary_max_per_second": result["loudness"]})
        write_json(ws.analysis / "silences.json", {"key": p_key, "threshold_db": SILENCE_DB,
                                                   "min_duration": SILENCE_MIN_S, "silences": result["silences"]})
        sheets = build_sheets(ffmpeg, ws, result["frames"], result["samples"], meta)
        sheets.update(key=p_key, interval=interval)
        write_json(ws.analysis / "sheets.json", sheets)
    scenes = read_json(ws.analysis / "scenes.json")["cuts"]
    loudness = read_json(ws.analysis / "loudness.json")["momentary_max_per_second"]
    silences = read_json(ws.analysis / "silences.json")["silences"]
    sheets = read_json(ws.analysis / "sheets.json")

    if worker is not None:
        worker.join()
        transcript = {"key": t_key, **t_result["data"]}
        if transcript.get("engine"):  # do not cache "skipped" results, so installing Whisper later works
            write_json(t_path, transcript)
        elif t_path.is_file():
            t_path.unlink()
    if transcript.get("skipped"):
        notes.append(f"Transcript skipped: {transcript['skipped']}")

    cands = candidates(duration, transcript, loudness, scenes, silences, top, min_len, max_len)
    write_json(ws.analysis / "candidates.json", {
        "based_on": "transcript" if transcript.get("segments") else "audio/scene structure only",
        "min_length": min_len, "max_length": max_len, "candidates": cands})

    return {
        "ok": True,
        "analysis_dir": str(ws.analysis),
        "transcript": {"engine": transcript.get("engine"), "segments": len(transcript.get("segments") or []),
                       "file": str(t_path) if t_path.is_file() else None},
        "scene_cuts": len(scenes),
        "silences": len(silences),
        "integrated_lufs": read_json(ws.analysis / "loudness.json").get("integrated_lufs"),
        "sample_interval_s": sheets.get("interval"),
        "contact_sheets": [s["file"] for s in sheets["sheets"]],
        "sheet_scale": sheets["scale"],
        "top_candidates": [{k: c[k] for k in ("rank", "start", "end", "length", "score", "reasons")} for c in cands[:5]],
        "notes": notes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("workspace", type=Path, help="outputs/<name> created by prepare.py")
    parser.add_argument("--model", default="small", help="Whisper model (tiny, base, small, medium, large-v3)")
    parser.add_argument("--language", help="Spoken language code, e.g. en (default: auto-detect)")
    parser.add_argument("--no-transcribe", action="store_true", help="Skip speech recognition")
    parser.add_argument("--subtitles", type=Path, help="Use an .srt/.vtt file as the transcript instead")
    parser.add_argument("--sheet-every", type=float, help="Seconds between contact-sheet frames (default: auto)")
    parser.add_argument("--top", type=int, default=10, help="Number of reel candidates (default 10)")
    parser.add_argument("--min-length", type=float, default=15.0)
    parser.add_argument("--max-length", type=float, default=60.0)
    parser.add_argument("--force", action="store_true", help="Ignore cached results")
    args = parser.parse_args()
    try:
        result = analyze(args.workspace, args.model, args.language, not args.no_transcribe, args.subtitles,
                         args.sheet_every, args.top, args.min_length, args.max_length, args.force)
    except ToolError as exc:
        fail(str(exc))
    emit(result)


if __name__ == "__main__":
    main()
