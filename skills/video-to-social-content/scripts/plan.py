#!/usr/bin/env python3
"""
plan.py - Load and validate outputs/<name>/plan.json, the only file the agent
writes by hand. Every other script derives file names, crops, fades and
checks from it.

plan.json format (times are source timestamps: seconds or HH:MM:SS.mmm):

{
  "reels": [
    {"id": "01", "slug": "insight", "start": "00:01:14.0", "end": "00:01:45.5",
     "ratio": "9:16", "subject_x": 960,            # optional, display pixels
     "subject_y": null,                            # optional, for narrow sources
     "subject_track": [{"t": "00:01:14", "x": 700}, {"t": "00:01:30", "x": 1200}],  # optional pan
     "genre": "Insight", "hook": "The $2M mistake", "canvas": false}
  ],
  "photos": [
    {"id": "01", "slug": "speaker", "time": "00:01:24.5", "ratio": "3:4",
     "subject_x": 900, "carousel": 1, "format": "jpg"}
  ]
}

Usage:
  plan.py <plan.json>      # validate and print the resolved plan
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common import (
    REEL_MAX_S, REEL_MIN_S, REEL_SOFT_MAX_S, REEL_SOFT_MIN_S, Workspace, canvas_filename,
    emit, fail, parse_time, photo_filename, read_json, reel_filename,
)
from crop_math import RATIOS, calculate_crop

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
REEL_KEYS = {"id", "slug", "start", "end", "ratio", "subject_x", "subject_y", "subject_track",
             "genre", "hook", "canvas", "notes", "tags"}
PHOTO_KEYS = {"id", "slug", "time", "ratio", "subject_x", "subject_y", "carousel", "theme",
              "format", "notes"}


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_subject(item: Dict[str, Any], where: str, errors: List[str]) -> bool:
    ok = True
    for key in ("subject_x", "subject_y"):
        if item.get(key) is not None and not _num(item[key]):
            errors.append(f"{where}: {key} must be a number of pixels or null")
            ok = False
    return ok


def track_offsets(track: List[Dict[str, Any]], clip_start: float, crop_w: int, width: int) -> List[Tuple[float, int]]:
    """Convert subject_track (absolute times, subject centre x) into clip-relative crop x offsets."""
    points = []
    for p in track:
        t = parse_time(p["t"]) - clip_start
        x = int(round(p["x"] - crop_w / 2))
        points.append((max(0.0, round(t, 3)), max(0, min(width - crop_w, x))))
    points.sort()
    return points


def resolve(plan: Dict[str, Any], meta: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """Return (resolved plan, errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []
    width, height = meta["width"], meta["height"]
    duration = meta.get("duration")

    if not isinstance(plan, dict):
        return {}, ["plan must be a JSON object"], []
    unknown = set(plan) - {"reels", "photos", "notes", "source"}
    if unknown:
        warnings.append(f"plan: ignoring unknown keys {sorted(unknown)}")
    reels_in = plan.get("reels", [])
    photos_in = plan.get("photos", [])
    if not isinstance(reels_in, list) or not isinstance(photos_in, list):
        return {}, ["'reels' and 'photos' must be lists"], []
    if not reels_in and not photos_in:
        errors.append("plan has no reels and no photos")

    resolved: Dict[str, Any] = {"reels": [], "photos": []}
    seen_files = set()

    for i, reel in enumerate(reels_in):
        where = f"reels[{i}]"
        if not isinstance(reel, dict):
            errors.append(f"{where}: must be an object")
            continue
        extra = set(reel) - REEL_KEYS
        if extra:
            warnings.append(f"{where}: ignoring unknown keys {sorted(extra)}")
        if not ID_RE.match(str(reel.get("id", ""))):
            errors.append(f"{where}: 'id' is required (letters, digits, - or _), e.g. \"01\"")
            continue
        where = f"reel {reel['id']}"
        ratio = reel.get("ratio", "9:16")
        if ratio not in RATIOS:
            errors.append(f"{where}: ratio must be one of {list(RATIOS)}")
            continue
        try:
            start, end = parse_time(reel.get("start")), parse_time(reel.get("end"))
        except ValueError as exc:
            errors.append(f"{where}: {exc} (start and end are required)")
            continue
        length = end - start
        if length <= 0:
            errors.append(f"{where}: end ({end:.2f}s) must be after start ({start:.2f}s)")
            continue
        if length < REEL_MIN_S or length > REEL_MAX_S:
            errors.append(f"{where}: length {length:.2f}s is outside the {REEL_MIN_S:g}-{REEL_MAX_S:g}s limit")
        elif length < REEL_SOFT_MIN_S or length > REEL_SOFT_MAX_S:
            warnings.append(f"{where}: length {length:.1f}s is outside the recommended {REEL_SOFT_MIN_S:g}-{REEL_SOFT_MAX_S:g}s")
        if duration is not None and end > duration + 0.05:
            errors.append(f"{where}: end {end:.2f}s is past the video's end ({duration:.2f}s)")
        if not _check_subject(reel, where, errors):
            continue
        crop = calculate_crop(width, height, ratio, reel.get("subject_x"), reel.get("subject_y"))
        track = None
        if reel.get("subject_track") is not None:
            raw = reel["subject_track"]
            if (not isinstance(raw, list) or len(raw) < 2
                    or not all(isinstance(p, dict) and "t" in p and _num(p.get("x")) for p in raw)):
                errors.append(f"{where}: subject_track must be a list of at least 2 {{\"t\": time, \"x\": pixels}} points")
            elif crop["crop_w"] >= width:
                warnings.append(f"{where}: subject_track ignored (the crop already spans the full width)")
            else:
                try:
                    track = track_offsets(raw, start, crop["crop_w"], width)
                except ValueError as exc:
                    errors.append(f"{where}: subject_track: {exc}")
        name = reel_filename(reel)
        if name in seen_files:
            errors.append(f"{where}: duplicate output file {name}")
        seen_files.add(name)
        resolved["reels"].append({
            **reel, "ratio": ratio, "start_s": round(start, 3), "end_s": round(end, 3),
            "duration_s": round(length, 3), "crop": crop, "track_offsets": track,
            "file": name, "canvas_file": canvas_filename(reel) if reel.get("canvas") else None,
        })

    for i, photo in enumerate(photos_in):
        where = f"photos[{i}]"
        if not isinstance(photo, dict):
            errors.append(f"{where}: must be an object")
            continue
        extra = set(photo) - PHOTO_KEYS
        if extra:
            warnings.append(f"{where}: ignoring unknown keys {sorted(extra)}")
        if not ID_RE.match(str(photo.get("id", ""))):
            errors.append(f"{where}: 'id' is required (letters, digits, - or _), e.g. \"01\"")
            continue
        where = f"photo {photo['id']}"
        ratio = photo.get("ratio", "3:4")
        if ratio not in RATIOS:
            errors.append(f"{where}: ratio must be one of {list(RATIOS)}")
            continue
        if photo.get("format", "jpg") not in ("jpg", "png"):
            errors.append(f"{where}: format must be 'jpg' or 'png'")
            continue
        try:
            t = parse_time(photo.get("time"))
        except ValueError as exc:
            errors.append(f"{where}: {exc} ('time' is required)")
            continue
        if duration is not None and t >= duration:
            errors.append(f"{where}: time {t:.2f}s is past the video's end ({duration:.2f}s)")
        if not _check_subject(photo, where, errors):
            continue
        crop = calculate_crop(width, height, ratio, photo.get("subject_x"), photo.get("subject_y"))
        name = photo_filename(photo)
        if name in seen_files:
            errors.append(f"{where}: duplicate output file {name}")
        seen_files.add(name)
        resolved["photos"].append({**photo, "ratio": ratio, "time_s": round(t, 3), "crop": crop, "file": name})

    return resolved, errors, warnings


def load(plan_path: Path) -> Tuple[Workspace, Dict[str, Any], Dict[str, Any], List[str], List[str]]:
    """Load plan.json and the sibling meta.json; return (workspace, meta, resolved, errors, warnings)."""
    plan_path = Path(plan_path)
    ws = Workspace(plan_path.parent)
    if not ws.meta.is_file():
        raise FileNotFoundError(f"{ws.meta} not found; run prepare.py first")
    meta = read_json(ws.meta)
    try:
        plan = read_json(plan_path)
    except ValueError as exc:
        return ws, meta, {}, [f"{plan_path} is not valid JSON: {exc}"], []
    resolved, errors, warnings = resolve(plan, meta)
    return ws, meta, resolved, errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        _, _, resolved, errors, warnings = load(args.plan)
    except FileNotFoundError as exc:
        fail(str(exc))
    emit({"valid": not errors, "errors": errors, "warnings": warnings, "plan": resolved})
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
