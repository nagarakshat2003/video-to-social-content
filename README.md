# Video to Social Content Plugin

[![Antigravity](https://img.shields.io/badge/Antigravity-Plugin-blue.svg)](https://antigravity.google)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Compatible-orange.svg)](https://anthropic.com)
[![OpenAI Codex](https://img.shields.io/badge/Codex-Compatible-black.svg)](https://openai.com)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)]()

Turn raw landscape footage or YouTube URLs into platform-ready **9:16 vertical reels** (for TikTok, Instagram Reels, YouTube Shorts) and **3:4 photo carousel stills**, complete with high-converting social media captions, hooks, and narrative metadata.

Engineered for universal compatibility across **Google Antigravity**, **Anthropic Claude Code**, and **OpenAI Codex**.

---

## Features

- **Subject-Aware Cropping (Never Blind Center-Crop):** Analyzes subject focal coordinates ($X_{subject}$) and dynamically aligns the 9:16 and 3:4 crop windows using the bundled `crop_math.py`.
- **Multi-Genre Moments:** Identifies contrasting timeline beats (high-energy action, insightful dialogue, humor, emotional peaks).
- **Quality-Preserving Encoding:** Encodes with `libx264`, CRF 16, slow presets, and audio fades (`afade`) without letterboxing or squashing.
- **Narrative Storytelling & Captions:** Generates scroll-stopping hooks, CTAs, relevant hashtags, on-screen text ideas, and multi-slide carousel stories in `captions.md`.
- **Pre-Delivery Quality Verification:** Checks dimensions, aspect ratios, audio streams with `ffprobe`, and extracts start/mid/end frames before completing tasks.
- **Content Ethics & Copyright Disclaimers:** Flags sensitive themes/violence with monetization warnings and includes copyright notices for third-party media.

---

## Prerequisites

The plugin utilizes local command-line tools executed via the host agent:

1. **FFmpeg & FFprobe** (Required):
   - **Linux:** `sudo apt-get install ffmpeg`
   - **macOS:** `brew install ffmpeg`
   - **Windows:** `winget install Gyan.FFmpeg` or `choco install ffmpeg`
2. **Python 3** (Required for `crop_math.py`):
   - Standard Python 3.8+ runtime.
3. **Whisper / Faster-Whisper** (Optional, for automatic dialogue transcription):
   - `pip install whisper-openai` or `pip install faster-whisper`

---

## Installation

### Google Antigravity
Clone or copy the directory to your Antigravity plugins directory or workspace:
```bash
# User-scoped global plugin
git clone https://github.com/your-org/video-to-social-content ~/.gemini/config/plugins/video-to-social-content
```
Or discover it directly from the Agent Marketplace.

### Anthropic Claude Code
Install the plugin directly using the Claude CLI:
```bash
claude plugin install /path/to/video-to-social-content
```

### OpenAI Codex
Install locally or register the repository as a marketplace:
```bash
# Direct local install
codex plugin install /path/to/video-to-social-content

# Or add repository marketplace
codex plugin marketplace add your-org/video-to-social-content --ref main
codex plugin add video-to-social-content@video-to-social-content-marketplace
```

---

## How to Use

Invoke the slash command or prompt in chat:

```text
/video-to-social-content path/to/podcast_interview.mp4
```

With custom instructions:
```text
/video-to-social-content interview.mp4 --focus "startup lessons" --reels 4 --platform "tiktok"
```

### Output Directory Structure

Deliverables are isolated non-destructively under:
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
├── samples/
└── captions.md
```

---

## Cross-Platform Architecture

```text
video-to-social-content/
├── plugin.json                              # Antigravity plugin manifest
├── .claude-plugin/
│   └── plugin.json                          # Claude Code plugin manifest
├── .codex-plugin/
│   └── plugin.json                          # Codex plugin manifest
├── .agents/
│   └── plugins/
│       └── marketplace.json                 # Codex marketplace catalog
├── AGENTS.md                                # Root operational rules (Codex & universal)
├── CLAUDE.md                                # Root project instructions (Claude Code)
├── README.md                                # Universal documentation
├── assets/
│   ├── logo.svg                             # Vector logo (Antigravity & Claude)
│   └── icon.png                             # 256x256 PNG raster icon (Codex & desktop UI)
├── commands/
│   └── video-to-social-content.md           # Claude Code explicit slash command
├── rules/
│   └── AGENTS.md                            # Antigravity always-on plugin rule
├── agents/
│   └── video-editor.md                      # Video slicing subagent (Antigravity & Claude)
└── skills/
    └── video-to-social-content/
        ├── SKILL.md                         # Portable procedural workflow
        └── scripts/
            └── crop_math.py                 # Mathematical crop geometry calculator
```

---

## License

MIT License.
