#!/usr/bin/env python3
"""
probe.py - Normalized video metadata from ffprobe.

Reports *display* dimensions (rotation already applied, because ffmpeg
auto-rotates frames on decode), duration from the container, frame rate,
codecs, and whether there is an audio stream.

Usage:
  probe.py <video> [--out meta.json]
"""

from __future__ import annotations

import argparse
import json
import os
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Optional

from common import ToolError, emit, fail, require, run, write_json


def _fps(stream: Dict[str, Any]) -> Optional[float]:
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = stream.get(key)
        if raw and raw not in ("0/0", "0"):
            try:
                value = float(Fraction(raw))
            except (ValueError, ZeroDivisionError):
                continue
            if value > 0:
                return round(value, 3)
    return None


def _normalize_rotation(degrees: float) -> int:
    """Map any rotation to (-180, 180], so 270 and -90 (reported by different ffmpeg versions) agree."""
    value = int(round(degrees)) % 360
    return value - 360 if value > 180 else value


def _rotation(stream: Dict[str, Any]) -> int:
    for item in stream.get("side_data_list", []) or []:
        if "rotation" in item:
            try:
                return _normalize_rotation(float(item["rotation"]))
            except (TypeError, ValueError):
                pass
    rotate = (stream.get("tags") or {}).get("rotate")  # ffmpeg < 5 stores it as a tag
    if rotate is not None:
        try:
            return _normalize_rotation(float(rotate))
        except ValueError:
            pass
    return 0


def probe(source: str) -> Dict[str, Any]:
    ffprobe = require("ffprobe", "Install ffmpeg (which includes ffprobe).")
    if not Path(source).is_file():
        raise ToolError(f"Video not found: {source}")
    entries = ("stream=index,codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,r_frame_rate,duration"
               ":stream_side_data=rotation:stream_tags=rotate:format=duration,size,format_name")
    proc = run([ffprobe, "-v", "error", "-show_entries", entries, "-of", "json", source], check=False)
    if proc.returncode != 0:  # very old ffprobe without the side-data section: rotation comes from tags only
        proc = run([ffprobe, "-v", "error", "-show_entries", entries.replace(":stream_side_data=rotation", ""),
                    "-of", "json", source])
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video" and s.get("width")), None)
    if video is None:
        raise ToolError(f"No video stream found in {source}")
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    rotation = _rotation(video)
    coded_w, coded_h = int(video["width"]), int(video["height"])
    if abs(rotation) % 180 == 90:
        width, height = coded_h, coded_w
    else:
        width, height = coded_w, coded_h

    fmt = data.get("format", {})
    duration = None
    for raw in (fmt.get("duration"), video.get("duration")):
        try:
            duration = float(raw)
            break
        except (TypeError, ValueError):
            continue

    return {
        "source": os.path.abspath(source),
        "width": width,
        "height": height,
        "coded_width": coded_w,
        "coded_height": coded_h,
        "rotation": rotation,
        "duration": duration,
        "fps": _fps(video),
        "video_codec": video.get("codec_name"),
        "pix_fmt": video.get("pix_fmt"),
        "has_audio": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "container": fmt.get("format_name"),
        "size_bytes": int(fmt["size"]) if fmt.get("size") else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video")
    parser.add_argument("--out", type=Path, help="Also write the metadata to this JSON file")
    args = parser.parse_args()
    try:
        meta = probe(args.video)
    except ToolError as exc:
        fail(str(exc))
    if args.out:
        write_json(args.out, meta)
    emit(meta)


if __name__ == "__main__":
    main()
