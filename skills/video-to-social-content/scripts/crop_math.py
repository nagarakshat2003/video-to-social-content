#!/usr/bin/env python3
"""
crop_math.py - Computes exact ffmpeg crop geometry for 9:16 vertical reels and 3:4 photos.
Ensures even pixel dimensions, bounds-clamping, and center/custom subject offset.

The crop always fits inside the source frame:
- Source wider than the target ratio  -> keep full height, crop width, offset on X.
- Source narrower than the target ratio -> keep full width, crop height, offset on Y.

Pass the *display* dimensions (after applying any 90/270 degree rotation metadata).
"""

import argparse

RATIOS = {
    "9:16": (9, 16),
    "3:4": (3, 4),
    "1:1": (1, 1),
}


def _even(value: int) -> int:
    return (value // 2) * 2


def calculate_crop(width: int, height: int, aspect_ratio: str, subject_x: int = None, subject_y: int = None):
    if aspect_ratio not in RATIOS:
        raise ValueError(f"Unsupported ratio: {aspect_ratio}")
    if width < 2 or height < 2:
        raise ValueError(f"Invalid source dimensions: {width}x{height}")
    ratio_w, ratio_h = RATIOS[aspect_ratio]

    # Compare aspect ratios with integer math: width/height >= ratio_w/ratio_h
    if width * ratio_h >= height * ratio_w:
        # Source is wider than (or equal to) the target: keep height, crop width.
        crop_h = _even(height)
        crop_w = _even(crop_h * ratio_w // ratio_h)

        if subject_x is not None:
            offset_x = subject_x - (crop_w // 2)
        else:
            offset_x = (width - crop_w) // 2
        offset_x = max(0, min(width - crop_w, offset_x))
        offset_y = (height - crop_h) // 2
    else:
        # Source is narrower than the target: keep width, crop height.
        crop_w = _even(width)
        crop_h = _even(crop_w * ratio_h // ratio_w)

        if subject_y is not None:
            offset_y = subject_y - (crop_h // 2)
        else:
            offset_y = (height - crop_h) // 2
        offset_y = max(0, min(height - crop_h, offset_y))
        offset_x = (width - crop_w) // 2

    if crop_w < 2 or crop_h < 2:
        raise ValueError(f"Source {width}x{height} is too small for a {aspect_ratio} crop")

    return {
        "crop_w": crop_w,
        "crop_h": crop_h,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "ffmpeg_filter": f"crop={crop_w}:{crop_h}:{offset_x}:{offset_y}",
        "resolution": f"{crop_w}x{crop_h}"
    }


def main():
    parser = argparse.ArgumentParser(description="Calculate subject-aware crop dimensions for ffmpeg.")
    parser.add_argument("--width", "-W", type=int, required=True, help="Source display width in pixels")
    parser.add_argument("--height", "-H", type=int, required=True, help="Source display height in pixels")
    parser.add_argument("--ratio", "-r", choices=list(RATIOS), default="9:16", help="Target aspect ratio")
    parser.add_argument("--subject-x", "-x", type=int, default=None, help="Subject focal point X coordinate")
    parser.add_argument("--subject-y", "-y", type=int, default=None, help="Subject focal point Y coordinate")

    args = parser.parse_args()
    try:
        result = calculate_crop(args.width, args.height, args.ratio, args.subject_x, args.subject_y)
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Target Resolution: {result['resolution']}")
    print(f"Crop Filter: {result['ffmpeg_filter']}")
    print(f"Width: {result['crop_w']}, Height: {result['crop_h']}, X: {result['offset_x']}, Y: {result['offset_y']}")


if __name__ == "__main__":
    main()
