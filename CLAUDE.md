# CLAUDE.md - Video to Social Content Project Instructions

This repository houses the **Video to Social Content** plugin for turning video footage and URLs into platform-ready 9:16 vertical reels, 3:4 photo carousels, and engaging captions.

## Quick Reference Commands

- **Run Crop Calculator:**
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT:-.}/skills/video-to-social-content/scripts/crop_math.py" --width <W> --height <H> --ratio 9:16 --subject-x <X>
  ```
- **Inspect Video Metadata:**
  ```bash
  ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,duration,codec_name -of json "source.mp4"
  ```

## Core Behavioral Guidelines

1. **Non-Destructive Operations:** Never modify the original video source file. Always write outputs to `outputs/<video-name>/reels/`, `outputs/<video-name>/photos/`, and `outputs/<video-name>/captions.md`.
2. **Subject-Aware Cropping (Never Blind Center-Crop):** Inspect sampled frames to locate primary subjects/faces and compute crop offset $x$. Use `crop_math.py` to ensure even integer pixel bounds.
3. **Encoding Quality:** Use `libx264`, `-crf 16`, `-preset slow`, `aac`, `-movflags +faststart`, with short audio fades (`afade`).
4. **Rigorous Verification:** Verify dimensions, aspect ratios, and audio presence with `ffprobe`. Extract and visually inspect start, middle, and end frames before completing tasks.
5. **Factual Integrity:** Never invent dialogue, speaker names, quotes, or locations not present in the footage.
6. **Ethics & Safety:** Never clip minors in sensitive contexts. Tag mature themes/violence and include copyright reminders for third-party media.
