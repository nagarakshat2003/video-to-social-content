# Video to Social Content Plugin for Antigravity

[![Antigravity Plugin](https://img.shields.io/badge/Antigravity-Plugin-blue.svg)](https://antigravity.google)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)]()

Turn any raw landscape video or YouTube URL into platform-ready **9:16 vertical reels** (for TikTok, Instagram Reels, YouTube Shorts) and **3:4 photo carousel stills**, complete with high-converting social media captions and metadata.

---

## Features

- **Subject-Aware Cropping (Never Blind Center-Crop):** Inspects subject position, facial focus, and motion vectors to dynamically position the 9:16 and 3:4 crop windows.
- **Multi-Genre Moments:** Identifies contrasting beats across the timeline (high-energy action, deep dialogue/insight, comedy, emotional peaks).
- **Quality-Preserving Encoding:** Uses `libx264`, CRF 16, slow presets, and audio fades (`afade`) without letterboxing or squashing.
- **Complete Captions & Carousel Storytelling:** Generates scroll-stopping hooks, CTA, hashtags, on-screen text ideas, and full narrative carousel captions compiled in `captions.md`.
- **Built-in Quality Verification:** Analyzes output dimensions, durations, audio tracks, and extracts start/mid/end sample frames to guarantee visual framing.
- **Safety & Rights Guardrails:** Flags sensitive themes (violence, mature content) with monetization warnings, and includes copyright reminders for third-party footage.

---

## Prerequisites

The plugin utilizes local command-line tools executed via Antigravity's `run_command`:

1. **FFmpeg & FFprobe** (Required):
   - **Windows:** `winget install Gyan.FFmpeg` or `choco install ffmpeg`
   - **macOS:** `brew install ffmpeg`
   - **Linux:** `sudo apt-get install ffmpeg`
2. **Whisper / Faster-Whisper** (Optional, for automatic speech recognition):
   - `pip install whisper-openai` or `pip install faster-whisper`

---

## How to Use

Invoke the slash command in chat or pass a video file:

```text
/video-to-social-content path/to/podcast_interview.mp4
```

Or provide extra instructions:
```text
/video-to-social-content interview.mp4 --focus "startup advice" --reels 4 --platform "tiktok"
```

### Outputs Structure

Deliverables are saved non-destructively under:
```text
outputs/<video-name>/
├── reels/
│   ├── reel_01_insight.mp4
│   ├── reel_02_humor.mp4
│   └── reel_03_action.mp4
├── photos/
│   ├── photo_01_slide1.jpg
│   ├── photo_02_slide2.jpg
│   └── photo_03_slide3.jpg
└── captions.md
```

---

## Plugin Architecture

```text
video-to-social-content/
├── plugin.json                              # Plugin manifest & suggested prompts
├── README.md                                # User documentation
├── assets/
│   └── logo.svg                             # Plugin icon
├── rules/
│   └── AGENTS.md                            # Always-on safety, non-destructive, and attribution rules
├── agents/
│   └── video-editor.md                      # Dedicated video slicing subagent
└── skills/
    └── video-to-social-content/
        ├── SKILL.md                         # Slash command & procedural guide
        └── scripts/
            └── crop_math.py                 # Mathematical crop geometry calculator
```

---

## License

MIT License. Designed for Antigravity & the Agent Marketplace.
