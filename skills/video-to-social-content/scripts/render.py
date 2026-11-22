#!/usr/bin/env python3
"""
render.py - Render every reel and photo in plan.json with the house encoding
standard (libx264 CRF 16 preset slow, yuv420p, AAC 192k, faststart, audio
fades). Crops, fades and file names are computed, never hand-typed.

Usage:
  render.py outputs/<name>/plan.json [--only ID ...] [--jobs N] [--preset slow]
                                     [--dry-run] [--force]

Writes outputs/<name>/render_report.json. Exits 2 if the plan is invalid.
Existing outputs are skipped unless --force (re-runs are cheap).
"""

from __future__ import annotations

import argparse
import shlex
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import plan as plan_mod
from common import (
    AUDIO_BITRATE, AUDIO_CODEC, CANVAS_H, CANVAS_W, PIX_FMT, VIDEO_CODEC, VIDEO_CRF, VIDEO_PRESET,
    ToolError, Workspace, emit, fail, require, run, write_json,
)


def _fmt(n: float) -> str:
    return f"{n:.3f}".rstrip("0").rstrip(".")


def track_expression(offsets: List[Tuple[float, int]]) -> str:
    """Piecewise-linear crop x expression over clip time t (seconds)."""
    expr = str(offsets[-1][1])
    for (t0, x0), (t1, x1) in reversed(list(zip(offsets, offsets[1:]))):
        if t1 > t0:
            seg = f"{x0}+({x1 - x0})*(t-{_fmt(t0)})/{_fmt(t1 - t0)}"
        else:
            seg = str(x1)
        expr = f"if(lt(t,{_fmt(t1)}),{seg},{expr})"
    t_first, x_first = offsets[0]
    if t_first > 0:
        expr = f"if(lt(t,{_fmt(t_first)}),{x_first},{expr})"
    return expr


def crop_filter(item: Dict[str, Any]) -> str:
    c = item["crop"]
    x = f"'{track_expression(item['track_offsets'])}'" if item.get("track_offsets") else str(c["offset_x"])
    return f"crop={c['crop_w']}:{c['crop_h']}:{x}:{c['offset_y']}"


def fade_filter(duration: float) -> str:
    fade_in = min(0.3, duration / 4)
    fade_out = min(0.5, duration / 4)
    return (f"afade=t=in:st=0:d={_fmt(fade_in)},"
            f"afade=t=out:st={_fmt(duration - fade_out)}:d={_fmt(fade_out)}")


def reel_command(ffmpeg: str, source: str, reel: Dict[str, Any], has_audio: bool, out: Path, preset: str) -> List[str]:
    cmd = [ffmpeg, "-hide_banner", "-v", "error", "-y",
           "-ss", _fmt(reel["start_s"]), "-i", source, "-t", _fmt(reel["duration_s"]),
           "-map", "0:v:0", "-vf", crop_filter(reel),
           "-c:v", VIDEO_CODEC, "-crf", VIDEO_CRF, "-preset", preset, "-pix_fmt", PIX_FMT]
    if has_audio:
        cmd += ["-map", "0:a:0", "-af", fade_filter(reel["duration_s"]),
                "-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE]
    cmd += ["-movflags", "+faststart", str(out)]
    return cmd


def canvas_command(ffmpeg: str, reel_path: Path, has_audio: bool, out: Path, preset: str) -> List[str]:
    graph = (f"[0:v]split[a][b];[a]scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,"
             f"crop={CANVAS_W}:{CANVAS_H},boxblur=20:20[bg];[bg][b]overlay=(W-w)/2:(H-h)/2,format={PIX_FMT}[v]")
    cmd = [ffmpeg, "-hide_banner", "-v", "error", "-y", "-i", str(reel_path),
           "-filter_complex", graph, "-map", "[v]",
           "-c:v", VIDEO_CODEC, "-crf", VIDEO_CRF, "-preset", preset]
    if has_audio:
        cmd += ["-map", "0:a:0", "-c:a", "copy"]
    cmd += ["-movflags", "+faststart", str(out)]
    return cmd


def photo_command(ffmpeg: str, source: str, photo: Dict[str, Any], out: Path) -> List[str]:
    cmd = [ffmpeg, "-hide_banner", "-v", "error", "-y", "-ss", _fmt(photo["time_s"]), "-i", source,
           "-frames:v", "1", "-vf", crop_filter(photo)]
    if out.suffix == ".jpg":
        cmd += ["-q:v", "1"]
    return cmd + [str(out)]


def render(plan_path: Path, only: Optional[List[str]] = None, jobs: int = 1, preset: str = VIDEO_PRESET,
           dry_run: bool = False, force: bool = False) -> Dict[str, Any]:
    ws, meta, resolved, errors, warnings = plan_mod.load(plan_path)
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}
    ffmpeg = require("ffmpeg", "Install ffmpeg first.")
    source = meta["source"]
    has_audio = bool(meta.get("has_audio"))
    ws.create()
    tasks = []  # (kind, item, out, [commands])

    for reel in resolved["reels"]:
        if only and reel["id"] not in only:
            continue
        out = ws.reels / reel["file"]
        cmds = [reel_command(ffmpeg, source, reel, has_audio, out, preset)]
        canvas_out = None
        if reel.get("canvas_file"):
            canvas_out = ws.reels / reel["canvas_file"]
            cmds.append(canvas_command(ffmpeg, out, has_audio, canvas_out, preset))
        tasks.append(("reel", reel, out, cmds, canvas_out))
    for photo in resolved["photos"]:
        if only and photo["id"] not in only:
            continue
        out = ws.photos / photo["file"]
        tasks.append(("photo", photo, out, [photo_command(ffmpeg, source, photo, out)], None))

    def execute(task):
        kind, item, out, cmds, canvas_out = task
        record = {
            "kind": kind, "id": item["id"], "file": str(out), "resolution": item["crop"]["resolution"],
            "crop_filter": crop_filter(item), "commands": [shlex.join(c) for c in cmds],
        }
        if kind == "reel":
            record.update(start=item["start_s"], end=item["end_s"], duration=item["duration_s"])
            if canvas_out:
                record["canvas_file"] = str(canvas_out)
        else:
            record["time"] = item["time_s"]
        if dry_run:
            record["status"] = "dry-run"
            return record
        targets = [out] + ([canvas_out] if canvas_out else [])
        if not force and all(p.is_file() and p.stat().st_size > 0 for p in targets):
            record["status"] = "skipped (exists; use --force to re-render)"
            return record
        try:
            for cmd in cmds:
                run(cmd)
            record["status"] = "rendered"
        except ToolError as exc:
            record["status"] = "failed"
            record["error"] = str(exc)
        return record

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        records = list(pool.map(execute, tasks))

    c_w = [t[1]["crop"] for t in tasks if t[0] == "reel"]
    if any(c["crop_w"] < CANVAS_W or c["crop_h"] < CANVAS_H for c in c_w):
        warnings.append(
            f"Some reels are below {CANVAS_W}x{CANVAS_H}. Tell the user the resolution and offer the "
            "blurred-background canvas (set \"canvas\": true on the reel and re-run) or upscaling.")
    report = {
        "ok": all(r["status"] != "failed" for r in records),
        "errors": [], "warnings": warnings, "items": records,
        "source": source, "preset": preset,
    }
    if not dry_run:
        write_json(ws.render_report, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--only", nargs="+", help="Render only these reel/photo ids")
    parser.add_argument("--jobs", type=int, default=1, help="Parallel ffmpeg processes (default 1)")
    parser.add_argument("--preset", default=VIDEO_PRESET,
                        help="x264 preset (default slow; use veryfast only for quick previews)")
    parser.add_argument("--dry-run", action="store_true", help="Print the commands without running them")
    parser.add_argument("--force", action="store_true", help="Re-render outputs that already exist")
    args = parser.parse_args()
    try:
        report = render(args.plan, args.only, args.jobs, args.preset, args.dry_run, args.force)
    except (ToolError, FileNotFoundError) as exc:
        fail(str(exc))
    emit(report)
    if report["errors"]:
        raise SystemExit(2)
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
