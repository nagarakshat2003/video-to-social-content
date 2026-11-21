#!/usr/bin/env python3
"""
crop_math.py - Computes exact ffmpeg crop geometry for 9:16 vertical reels and 3:4 photos.
Ensures even pixel dimensions, bounds-clamping, and center/custom subject offset.
"""

import sys
import argparse
import math

def calculate_crop(width: int, height: int, aspect_ratio: str, subject_x: int = None, subject_y: int = None):
    # Supported ratios
    if aspect_ratio == "9:16":
        target_w_ratio, target_h_ratio = 9, 16
    elif aspect_ratio == "3:4":
        target_w_ratio, target_h_ratio = 3, 4
    elif aspect_ratio == "1:1":
        target_w_ratio, target_h_ratio = 1, 1
    else:
        raise ValueError(f"Unsupported ratio: {aspect_ratio}")

    # For standard landscape footage (W > H):
    # Keep full height H and compute cropped width w
    if width >= height:
        crop_h = height
        crop_w = int(math.floor(height * target_w_ratio / target_h_ratio))
        # Ensure even numbers
        crop_w = (crop_w // 2) * 2
        crop_h = (crop_h // 2) * 2

        # Calculate x offset based on subject position
        if subject_x is not None:
            offset_x = subject_x - (crop_w // 2)
        else:
            offset_x = (width - crop_w) // 2

        # Clamp x offset within [0, width - crop_w]
        offset_x = max(0, min(width - crop_w, offset_x))
        offset_y = 0
    else:
        # Source is portrait / vertical:
        # Keep full width W and compute cropped height h
        crop_w = width
        crop_h = int(math.floor(width * target_h_ratio / target_w_ratio))
        crop_w = (crop_w // 2) * 2
        crop_h = (crop_h // 2) * 2

        if subject_y is not None:
            offset_y = subject_y - (crop_h // 2)
        else:
            offset_y = (height - crop_h) // 2

        offset_y = max(0, min(height - crop_h, offset_y))
        offset_x = 0

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
    parser.add_argument("--width", "-W", type=int, required=True, help="Source video width in pixels")
    parser.add_argument("--height", "-H", type=int, required=True, help="Source video height in pixels")
    parser.add_argument("--ratio", "-r", choices=["9:16", "3:4", "1:1"], default="9:16", help="Target aspect ratio")
    parser.add_argument("--subject-x", "-x", type=int, default=None, help="Subject focal point X coordinate")
    parser.add_argument("--subject-y", "-y", type=int, default=None, help="Subject focal point Y coordinate")

    args = parser.parse_args()
    result = calculate_crop(args.width, args.height, args.ratio, args.subject_x, args.subject_y)
    
    print(f"Target Resolution: {result['resolution']}")
    print(f"Crop Filter: {result['ffmpeg_filter']}")
    print(f"Width: {result['crop_w']}, Height: {result['crop_h']}, X: {result['offset_x']}, Y: {result['offset_y']}")

if __name__ == "__main__":
    main()
