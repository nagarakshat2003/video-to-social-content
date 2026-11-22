---
description: Extract 9:16 vertical reels and 3:4 photo carousels with engaging captions from video footage
---

# Video to Social Content Command

Extract viral 9:16 vertical reels, 3:4 photo carousel stills, and storytelling captions from the specified video file or URL.

## Instructions

1. Refer to the end-to-end procedural workflow in `skills/video-to-social-content/SKILL.md`.
2. Adhere strictly to the non-destructive and subject-aware cropping guidelines in `AGENTS.md`.
3. Process the input video provided in the user request (or prompt for one if missing).
4. Save all deliverables non-destructively under `outputs/<video-name>/reels/`, `outputs/<video-name>/photos/`, and `outputs/<video-name>/captions.md`.
5. Verify outputs using `ffprobe` and sample keyframes before presenting the final summary.
