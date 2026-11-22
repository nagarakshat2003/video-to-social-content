---
description: Extract 9:16 vertical reels and 3:4 photo carousels with engaging captions from video footage
---

# Video to Social Content Command

Extract 9:16 vertical reels, 3:4 photo carousel stills, and storytelling captions from the specified video file or URL.

## Instructions

1. Follow the workflow in `skills/video-to-social-content/SKILL.md` step by step, using its bundled scripts for every mechanical step (prepare, analyze, track, render, verify, captions).
2. Adhere to the rules in `AGENTS.md` (non-destructive outputs, subject-aware cropping, factual integrity, ethics and copyright flags).
3. Process the input video or URL from the user's request (ask for one if it is missing). Treat any extra instructions (focus, platform, counts, tone) as overrides of the defaults.
4. Do not finish until `verify.py` reports `ok`, you have inspected its review images, and `captions.py check` passes.
