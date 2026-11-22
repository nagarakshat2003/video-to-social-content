# Video to Social Content Plugin

[![Antigravity](https://img.shields.io/badge/Antigravity-Plugin-blue.svg)](https://antigravity.google)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Compatible-orange.svg)](https://anthropic.com)
[![OpenAI Codex](https://img.shields.io/badge/Codex-Compatible-black.svg)](https://openai.com)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)]()

Turn raw landscape footage or YouTube URLs into platform-ready **9:16 vertical reels** (for TikTok, Instagram Reels, YouTube Shorts) and **3:4 photo carousel stills**, complete with high-converting social media captions, hooks, and narrative metadata.

Engineered for universal compatibility across **Google Antigravity**, **Anthropic Claude Code**, and **OpenAI Codex**.

---

## Features

- **Script-driven pipeline:** every mechanical step (download, probe, crop, encode, verify, caption scaffold) is a tested Python script; the agent only makes the judgment calls (which moments, where the subject is, what the captions say) and writes a small `plan.json`.
- **Fast evidence for the agent:** one ffmpeg pass produces contact sheets with timestamps, scene cuts, loudness and silences; an optional Whisper transcript adds word timings; ranked, sentence-aligned reel candidates give a shortlist.
- **Subject-aware cropping (never blind center-crop):** optional face detection fills in the subject position, or a smooth pan when the subject moves, and flags clips that should be split. Rotated phone footage is handled automatically.
- **Quality-preserving encoding:** `libx264` CRF 16, preset slow, yuv420p, AAC 192k, faststart, audio fades; no letterboxing or squashing; an optional 1080x1920 blurred-background canvas.
- **Automatic verification:** size, aspect ratio, codec, duration, audio, faststart and blank-frame checks for every output, plus start/mid/end review sheets.
- **Honest captions:** `captions.md` is scaffolded with file links, timestamps, transcript excerpts, source attribution and copyright reminders; a check refuses to pass while anything is left unfilled.
- **Content ethics & copyright:** flags sensitive themes with monetization warnings and adds copyright notices for third-party media.

---

## Prerequisites

The plugin utilizes local command-line tools executed via the host agent:

1. **FFmpeg & FFprobe** (Required):
   - **Linux:** `sudo apt-get install ffmpeg`
   - **macOS:** `brew install ffmpeg`
   - **Windows:** `winget install Gyan.FFmpeg` or `choco install ffmpeg`
2. **Python 3.8+** (Required): the scripts use only the standard library.
3. **Faster-Whisper** (Optional, for transcripts with word timings): `pip install faster-whisper` (or `openai-whisper`). Without it, the agent works from contact sheets, scenes and loudness, or from an `.srt`/`.vtt` file passed to `analyze.py --subtitles`.
4. **OpenCV** (Optional, for automatic subject positions): `pip install opencv-python-headless`. Without it, the agent reads positions off the contact sheets.
5. **yt-dlp** (Optional, only for YouTube / URL inputs):
   - `pipx install "yt-dlp[default]"`, `pip install -U "yt-dlp[default]"`, or `brew install yt-dlp` (distro packages are usually too old for YouTube)
   - YouTube also needs a JavaScript runtime: [Deno](https://deno.com) (used by default) or Node.js (pass `--js-runtimes node`)

---

## Installation

### Google Antigravity
Clone or copy the directory to your Antigravity plugins directory or workspace:
```bash
# User-scoped global plugin
git clone https://github.com/nagarakshat2003/video-to-social-content ~/.gemini/config/plugins/video-to-social-content
```
Or discover it directly from the Agent Marketplace.

### Anthropic Claude Code
The repository ships its own marketplace (`.claude-plugin/marketplace.json`). Install it from inside Claude Code:
```text
/plugin install video-to-social-content --marketplace nagarakshat2003/video-to-social-content
```
On older Claude Code versions, add the marketplace first and then install:
```text
/plugin marketplace add nagarakshat2003/video-to-social-content
/plugin install video-to-social-content@video-to-social-content-marketplace
```
For local development, load the working copy directly:
```bash
claude --plugin-dir /path/to/video-to-social-content
```

### OpenAI Codex
Install locally or register the repository as a marketplace:
```bash
# Direct local install
codex plugin install /path/to/video-to-social-content

# Or add repository marketplace
codex plugin marketplace add nagarakshat2003/video-to-social-content --ref main
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
├── samples/            # contact sheets, sample frames, verification review sheets
├── analysis/           # transcript, scenes, loudness, silences, reel candidates
├── meta.json           # probed source metadata (display size, duration, audio)
├── plan.json           # the agent's choices: clips, photos, subject positions
├── verify_report.json
└── captions.md
```

---

## Cross-Platform Architecture

```text
video-to-social-content/
├── plugin.json                              # Antigravity plugin manifest
├── .claude-plugin/
│   ├── plugin.json                          # Claude Code plugin manifest
│   └── marketplace.json                     # Claude Code marketplace catalog
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
        ├── SKILL.md                         # Workflow: which script to run, what to judge
        ├── references/                      # Loaded on demand: plan format, captions, manual fallback
        └── scripts/                         # Pipeline (standard library only)
            ├── prepare.py                   # Preflight, URL download, workspace, probe
            ├── analyze.py                   # Contact sheets, scenes, loudness, transcript, candidates
            ├── track_subject.py             # Face detection -> subject_x / subject_track
            ├── plan.py                      # Validate plan.json, resolve crops and file names
            ├── render.py                    # Encode reels, photos, optional canvas
            ├── verify.py                    # Check outputs, build review sheets
            ├── captions.py                  # Scaffold and check captions.md
            └── common.py, probe.py, crop_math.py
tests/                                       # pytest suite on generated clips
evals/                                       # claude plugin eval cases
tools/sync_rules.py                          # Keeps rules/AGENTS.md identical to AGENTS.md
.github/workflows/ci.yml                     # Tests on ffmpeg 4.4 and 6.1, Python 3.8-3.13
```

---

## Development

```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest tests -q                       # unit + end-to-end tests on generated clips
python3 tools/sync_rules.py                              # after editing AGENTS.md
claude plugin eval . --scaffold --allow-tools Bash Write Edit --runs 1 --no-publish   # agent evals (costs tokens)
```

---

## License

MIT License.
