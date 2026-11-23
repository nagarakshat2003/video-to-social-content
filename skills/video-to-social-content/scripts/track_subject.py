#!/usr/bin/env python3
"""
track_subject.py - Fill in subject positions in plan.json from face detection.

For every reel and photo that has no subject position yet (or all of them
with --all), samples frames over the clip, detects faces with OpenCV's
bundled Haar cascades (frontal + profile, no model download), and decides:

  static   subject stays put        -> sets subject_x (or subject_y for narrow sources)
  pan      subject drifts smoothly  -> sets subject_track (reels only)
  split    subject jumps back and forth (e.g. two speakers) -> no change, flagged
  none     too few faces found      -> no change, flagged (place it yourself)

Without --write it only reports. With --write it updates plan.json and keeps
the previous version as plan.json.bak. Always confirm the result on the
verify.py review images.

Requires: pip install opencv-python-headless

Usage:
  track_subject.py outputs/<name>/plan.json [--write] [--all]
"""

from __future__ import annotations

import argparse
import shutil
import statistics
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import plan as plan_mod
from common import ToolError, emit, fail, read_json, require, write_json

ANALYSIS_WIDTH = 640
MAX_SAMPLES = 16
MIN_HIT_RATE = 0.3
STATIC_SPREAD = 0.25   # x spread below this fraction of crop width -> static crop
JUMP_FRACTION = 0.6    # a jump of more than this fraction of crop width between samples is a cut, not a pan
MAX_TRACK_POINTS = 8

Box = Tuple[float, float, float, float]  # x, y, w, h in source display pixels


# --------------------------------------------------------------------------- pure decision logic

def pick_primary(faces: Sequence[Box], prev_center: Optional[float]) -> Optional[Box]:
    """Largest face, unless one at least 60% as large sits much closer to the previous position."""
    if not faces:
        return None
    largest = max(faces, key=lambda f: f[2] * f[3])
    if prev_center is None:
        return largest
    near = [f for f in faces if f[2] * f[3] >= 0.6 * largest[2] * largest[3]]
    return min(near, key=lambda f: abs(f[0] + f[2] / 2 - prev_center))


def _median3(values: List[float]) -> List[float]:
    if len(values) < 3:
        return list(values)
    out = [values[0]]
    out += [statistics.median(values[i - 1:i + 2]) for i in range(1, len(values) - 1)]
    return out + [values[-1]]


def _simplify(points: List[Tuple[float, float]], tolerance: float) -> List[Tuple[float, float]]:
    """Keep the endpoints plus points where the path bends by more than tolerance (Ramer-Douglas-Peucker on x)."""
    if len(points) <= 2:
        return points
    (t0, x0), (t1, x1) = points[0], points[-1]
    worst, idx = 0.0, 0
    for i, (t, x) in enumerate(points[1:-1], start=1):
        expected = x0 + (x1 - x0) * (t - t0) / (t1 - t0) if t1 > t0 else x0
        if abs(x - expected) > worst:
            worst, idx = abs(x - expected), i
    if worst <= tolerance:
        return [points[0], points[-1]]
    return _simplify(points[:idx + 1], tolerance)[:-1] + _simplify(points[idx:], tolerance)


def decide(samples: List[Tuple[float, Optional[float]]], crop_size: int, axis: str, allow_track: bool) -> Dict[str, Any]:
    """samples: (source time, subject centre on the cropped axis or None)."""
    hits = [(t, c) for t, c in samples if c is not None]
    rate = len(hits) / len(samples) if samples else 0.0
    base = {"frames": len(samples), "detections": len(hits), "hit_rate": round(rate, 2)}
    if not hits or rate < MIN_HIT_RATE:
        return {**base, "decision": "none", "reason": "too few faces detected; place the subject from the sheets"}
    times = [t for t, _ in hits]
    centres = _median3([c for _, c in hits])
    spread = max(centres) - min(centres)
    median = int(round(statistics.median(centres)))
    key = f"subject_{axis}"
    if spread <= STATIC_SPREAD * crop_size or len(hits) < 3:
        return {**base, "decision": "static", key: median, "spread_px": int(spread)}
    jumps = sum(1 for a, b in zip(centres, centres[1:]) if abs(b - a) > JUMP_FRACTION * crop_size)
    if jumps >= 2 or not allow_track or axis != "x":
        return {**base, "decision": "split", key: median, "spread_px": int(spread), "jumps": jumps,
                "reason": "subject jumps between positions (several people or cuts); split the clip or choose "
                          "one subject" if jumps >= 2 else "subject moves but only reels on the x axis can pan"}
    points = _simplify(list(zip(times, centres)), 0.05 * crop_size)[:MAX_TRACK_POINTS]
    return {**base, "decision": "pan", "spread_px": int(spread),
            "subject_track": [{"t": round(t, 3), "x": int(round(x))} for t, x in points]}


# --------------------------------------------------------------------------- detection

def load_detectors():
    try:
        import cv2  # type: ignore
    except ImportError:
        raise ToolError("Face detection needs OpenCV: pip install opencv-python-headless. "
                        "Without it, read subject positions off the contact sheets (see SKILL.md Step 3).")
    root = Path(cv2.data.haarcascades)
    frontal = cv2.CascadeClassifier(str(root / "haarcascade_frontalface_default.xml"))
    profile = cv2.CascadeClassifier(str(root / "haarcascade_profileface.xml"))
    return cv2, frontal, profile


def detect_faces(detectors, image: Path, scale: float) -> List[Box]:
    cv2, frontal, profile = detectors
    img = cv2.imread(str(image))
    if img is None:
        return []
    gray = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    min_side = max(24, img.shape[1] // 25)
    found = list(frontal.detectMultiScale(gray, 1.1, 5, minSize=(min_side, min_side)))
    if not found:
        found = list(profile.detectMultiScale(gray, 1.1, 5, minSize=(min_side, min_side)))
        if not found:  # profile cascade only finds one direction; try the mirror image
            flipped = cv2.flip(gray, 1)
            found = [(img.shape[1] - x - w, y, w, h) for x, y, w, h in
                     profile.detectMultiScale(flipped, 1.1, 5, minSize=(min_side, min_side))]
    return [(x * scale, y * scale, w * scale, h * scale) for x, y, w, h in found]


def sample_times(start: float, end: float) -> List[float]:
    length = max(0.0, end - start)
    if length == 0:
        return [start]
    step = max(0.5, length / MAX_SAMPLES)
    n = int(length // step) + 1
    return [round(min(end - 0.05, start + i * step), 3) for i in range(n)]


def extract(ffmpeg: str, source: str, t: float, out: Path) -> bool:
    proc = subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", source, "-frames:v", "1",
                           "-vf", f"scale={ANALYSIS_WIDTH}:-2", str(out)],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0 and out.is_file()


def track(plan_path: Path, write: bool = False, redo_all: bool = False, detectors=None) -> Dict[str, Any]:
    ws, meta, resolved, errors, _ = plan_mod.load(plan_path)
    if errors:
        return {"ok": False, "errors": errors, "items": []}
    detectors = detectors or load_detectors()
    ffmpeg = require("ffmpeg")
    work = ws.samples / "track"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    scale = meta["width"] / ANALYSIS_WIDTH
    raw_plan = read_json(plan_path)
    items: List[Dict[str, Any]] = []

    jobs = [("reel", r, raw_plan["reels"][i]) for i, r in enumerate(resolved["reels"])]
    jobs += [("photo", p, raw_plan["photos"][i]) for i, p in enumerate(resolved["photos"])]
    for kind, item, raw in jobs:
        has_position = any(raw.get(k) is not None for k in ("subject_x", "subject_y", "subject_track"))
        if has_position and not redo_all:
            items.append({"kind": kind, "id": item["id"], "decision": "kept", "reason": "already has a position"})
            continue
        crop = item["crop"]
        axis = "x" if crop["crop_w"] < meta["width"] else "y"
        if crop["crop_w"] >= meta["width"] and crop["crop_h"] >= meta["height"]:
            items.append({"kind": kind, "id": item["id"], "decision": "kept", "reason": "crop covers the whole frame"})
            continue
        times = sample_times(item["start_s"], item["end_s"]) if kind == "reel" else [item["time_s"]]
        samples: List[Tuple[float, Optional[float]]] = []
        prev = None
        for n, t in enumerate(times):
            frame = work / f"{kind}_{item['id']}_{n:02d}.jpg"
            faces = detect_faces(detectors, frame, scale) if extract(ffmpeg, meta["source"], t, frame) else []
            primary = pick_primary(faces, prev)
            centre = None
            if primary:
                centre = primary[0] + primary[2] / 2 if axis == "x" else primary[1] + primary[3] / 2
                prev = centre if axis == "x" else prev
            samples.append((t, centre))
        result = decide(samples, crop["crop_w"] if axis == "x" else crop["crop_h"], axis, allow_track=kind == "reel")
        result.update(kind=kind, id=item["id"])
        if write and result["decision"] in ("static", "pan"):
            for k in ("subject_x", "subject_y", "subject_track"):
                raw.pop(k, None)
            for k in ("subject_x", "subject_y", "subject_track"):
                if k in result:
                    raw[k] = result[k]
            result["written"] = True
        items.append(result)

    if write and any(i.get("written") for i in items):
        shutil.copyfile(plan_path, str(plan_path) + ".bak")
        write_json(plan_path, raw_plan)
    flagged = [i for i in items if i["decision"] in ("none", "split")]
    return {
        "ok": True, "errors": [], "written": write,
        "items": items,
        "needs_attention": [f"{i['kind']} {i['id']}: {i['decision']} ({i.get('reason', '')})" for i in flagged],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--write", action="store_true", help="Update plan.json (backup in plan.json.bak)")
    parser.add_argument("--all", action="store_true", help="Also redo items that already have a position")
    args = parser.parse_args()
    try:
        result = track(args.plan, args.write, args.all)
    except (ToolError, FileNotFoundError) as exc:
        fail(str(exc))
    emit(result)
    if result["errors"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
