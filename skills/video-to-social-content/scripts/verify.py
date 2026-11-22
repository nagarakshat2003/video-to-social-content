#!/usr/bin/env python3
"""
verify.py - Check every output in plan.json and build review sheets.

Per reel: exists, exact crop size, even dimensions, aspect ratio, H.264 +
yuv420p, duration matches the plan, audio present when the source has
audio, faststart (moov before mdat), and start/mid/end frames that are not
blank. Per photo: exact size, decodable, not blank. Canvas versions must be
1080x1920. Files in reels/ or photos/ that the plan does not list are
reported as stale.

Review images for the agent (look at these instead of individual frames):
  samples/verify/<reel>_sheet.jpg   start | mid | end of each reel
  samples/verify/photos_sheet_N.jpg  up to 5 photos per sheet

Usage:
  verify.py outputs/<name>/plan.json

Writes outputs/<name>/verify_report.json. Exit 0 = all checks passed,
1 = failures, 2 = invalid plan.
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import plan as plan_mod
from common import CANVAS_H, CANVAS_W, ToolError, chunks, emit, fail, require, run, write_json
from crop_math import RATIOS

SHEET_HEIGHT = 480
RATIO_TOLERANCE = 0.01


def stream_info(ffprobe: str, path: Path) -> Dict[str, Any]:
    proc = run([ffprobe, "-v", "error", "-show_entries",
                "stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate:format=duration",
                "-of", "json", str(path)])
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        duration = float(data.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        duration = None
    return {"video": video, "audio": audio, "duration": duration}


def moov_before_mdat(path: Path) -> Optional[bool]:
    """Walk top-level MP4 boxes; True if moov precedes mdat (faststart)."""
    try:
        with open(path, "rb") as fh:
            offset = 0
            size_total = path.stat().st_size
            while offset < size_total:
                fh.seek(offset)
                header = fh.read(8)
                if len(header) < 8:
                    return None
                size, kind = struct.unpack(">I4s", header)
                if size == 1:
                    size = struct.unpack(">Q", fh.read(8))[0]
                elif size == 0:
                    size = size_total - offset
                if kind == b"moov":
                    return True
                if kind == b"mdat":
                    return False
                if size < 8:
                    return None
                offset += size
    except OSError:
        return None
    return None


def mean_luma(ffmpeg: str, image: Path) -> Optional[float]:
    proc = subprocess.run([ffmpeg, "-v", "error", "-i", str(image), "-vf", "scale=1:1:flags=area,format=gray",
                           "-f", "rawvideo", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return float(proc.stdout[0]) if proc.returncode == 0 and proc.stdout else None


def extract_frame(ffmpeg: str, video: Path, out: Path, where: str, duration: float) -> bool:
    if where == "start":
        seek: List[str] = []
    elif where == "mid":
        seek = ["-ss", f"{duration / 2:.3f}"]
    else:
        seek = ["-sseof", "-0.1"]
    proc = subprocess.run([ffmpeg, "-v", "error", "-y", *seek, "-i", str(video), "-frames:v", "1", str(out)],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0 and out.is_file() and out.stat().st_size > 0


def build_sheet(ffmpeg: str, images: List[Path], out: Path) -> bool:
    if not images:
        return False
    inputs: List[str] = []
    for img in images:
        inputs += ["-i", str(img)]
    scaled = "".join(f"[{i}:v]scale=-2:{SHEET_HEIGHT}[s{i}];" for i in range(len(images)))
    labels = "".join(f"[s{i}]" for i in range(len(images)))
    graph = scaled + (f"{labels}hstack=inputs={len(images)}[out]" if len(images) > 1 else "[s0]null[out]")
    proc = subprocess.run([ffmpeg, "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[out]",
                           "-frames:v", "1", "-q:v", "3", str(out)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0


def check_size(result: Dict[str, Any], video: Dict[str, Any], want_w: int, want_h: int, ratio: Optional[str]) -> None:
    w, h = video.get("width"), video.get("height")
    result["resolution"] = f"{w}x{h}" if w else None
    if (w, h) != (want_w, want_h):
        result["failures"].append(f"size {w}x{h}, expected {want_w}x{want_h}")
        return
    if w % 2 or h % 2:
        result["failures"].append(f"odd dimensions {w}x{h}")
    if ratio:
        rw, rh = RATIOS[ratio]
        actual, target = w / h, rw / rh
        if abs(actual - target) / target > RATIO_TOLERANCE:
            result["failures"].append(f"aspect {actual:.4f} differs from {ratio} by more than 1%")


def check_frames(ffmpeg: str, result: Dict[str, Any], frames: List[Path]) -> None:
    for frame in frames:
        luma = mean_luma(ffmpeg, frame)
        if luma is None:
            result["failures"].append(f"could not read {frame.name}")
        elif luma < 12:
            result["warnings"].append(f"{frame.name} is almost black (mean luma {luma:.0f})")
        elif luma > 245:
            result["warnings"].append(f"{frame.name} is almost white (mean luma {luma:.0f})")


def verify(plan_path: Path) -> Dict[str, Any]:
    ws, meta, resolved, errors, warnings = plan_mod.load(plan_path)
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings, "items": []}
    ffmpeg = require("ffmpeg")
    ffprobe = require("ffprobe")
    ws.verify.mkdir(parents=True, exist_ok=True)
    items: List[Dict[str, Any]] = []

    for reel in resolved["reels"]:
        path = ws.reels / reel["file"]
        result: Dict[str, Any] = {"kind": "reel", "id": reel["id"], "file": str(path), "failures": [], "warnings": []}
        items.append(result)
        if not path.is_file() or path.stat().st_size == 0:
            result["failures"].append("missing (run render.py)")
            continue
        info = stream_info(ffprobe, path)
        video = info["video"]
        check_size(result, video, reel["crop"]["crop_w"], reel["crop"]["crop_h"], reel["ratio"])
        if video.get("codec_name") != "h264":
            result["failures"].append(f"video codec {video.get('codec_name')}, expected h264")
        if video.get("pix_fmt") != "yuv420p":
            result["failures"].append(f"pixel format {video.get('pix_fmt')}, expected yuv420p")
        fps = meta.get("fps") or 30
        duration = info["duration"]
        result["duration"] = duration
        tolerance = 0.1 + 2 / fps
        if duration is None or abs(duration - reel["duration_s"]) > tolerance:
            result["failures"].append(f"duration {duration}, planned {reel['duration_s']:.3f}s (±{tolerance:.2f})")
        if meta.get("has_audio") and not info["audio"]:
            result["failures"].append("no audio stream, but the source has audio")
        result["has_audio"] = bool(info["audio"])
        if moov_before_mdat(path) is False:
            result["failures"].append("not faststart (moov after mdat)")
        stem = path.stem
        frames = []
        for where in ("start", "mid", "end"):
            frame = ws.verify / f"{stem}_{where}.jpg"
            if extract_frame(ffmpeg, path, frame, where, duration or reel["duration_s"]):
                frames.append(frame)
            else:
                result["failures"].append(f"could not extract the {where} frame")
        check_frames(ffmpeg, result, frames)
        sheet = ws.verify / f"{stem}_sheet.jpg"
        if build_sheet(ffmpeg, frames, sheet):
            result["sheet"] = str(sheet)
        if reel.get("canvas_file"):
            canvas = ws.reels / reel["canvas_file"]
            if not canvas.is_file():
                result["failures"].append(f"canvas version {canvas.name} missing")
            else:
                cv = stream_info(ffprobe, canvas)["video"]
                if (cv.get("width"), cv.get("height")) != (CANVAS_W, CANVAS_H):
                    result["failures"].append(f"canvas is {cv.get('width')}x{cv.get('height')}, expected {CANVAS_W}x{CANVAS_H}")

    photo_paths: List[Path] = []
    for photo in resolved["photos"]:
        path = ws.photos / photo["file"]
        result = {"kind": "photo", "id": photo["id"], "file": str(path), "failures": [], "warnings": []}
        items.append(result)
        if not path.is_file() or path.stat().st_size == 0:
            result["failures"].append("missing (run render.py)")
            continue
        check_size(result, stream_info(ffprobe, path)["video"], photo["crop"]["crop_w"], photo["crop"]["crop_h"], photo["ratio"])
        check_frames(ffmpeg, result, [path])
        photo_paths.append(path)

    sheets = []
    for n, group in enumerate(chunks(photo_paths, 5), start=1):
        sheet = ws.verify / f"photos_sheet_{n}.jpg"
        if build_sheet(ffmpeg, group, sheet):
            sheets.append(str(sheet))

    expected = {reel["file"] for reel in resolved["reels"]} | {r["canvas_file"] for r in resolved["reels"] if r.get("canvas_file")}
    expected |= {p["file"] for p in resolved["photos"]}
    stale = sorted(p.name for d in (ws.reels, ws.photos) if d.is_dir() for p in d.iterdir()
                   if p.is_file() and p.name not in expected)
    if stale:
        warnings.append(f"files not in the plan (stale outputs?): {stale}")

    report = {
        "ok": all(not item["failures"] for item in items),
        "errors": [], "warnings": warnings,
        "passed": sum(1 for i in items if not i["failures"]),
        "failed": sum(1 for i in items if i["failures"]),
        "review_images": [i["sheet"] for i in items if i.get("sheet")] + sheets,
        "items": items,
    }
    write_json(ws.verify_report, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.plan)
    except (ToolError, FileNotFoundError) as exc:
        fail(str(exc))
    emit(report)
    if report["errors"]:
        raise SystemExit(2)
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
