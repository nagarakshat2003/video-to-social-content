---
name: video-to-social-content
description: Find the best moments from a video file or YouTube video and deliver 9:16 reel clips and 3:4 photos cropped from the source, with social media captions.
---

# Video to Social Content

Turns a video file or URL into 9:16 vertical reels, 3:4 photo carousels and a `captions.md`, using bundled scripts for every mechanical step. **Your job is the judgment:** which moments to cut, where the subject is, and what the captions say. The scripts handle downloading, probing, cropping, encoding, verification and the caption scaffold, so never hand-write ffmpeg commands unless the scripts cannot run (then see `references/manual-commands.md`).

## Scope & defaults

- **Trigger:** `/video-to-social-content`, `$video-to-social-content`, or any request to turn a video into reels, shorts, clips, stills or carousels.
- **Input:** a local video (`.mp4`, `.mov`, `.mkv`, …) or a URL. User instructions (focus, platform, tone, counts) override the defaults.
- **Defaults:** 3–6 reels of 15–60 s (hard cap 90 s); 6–10 photos in 1–3 carousels of 3–4; `captions.md` plus a summary table in chat.
- **Delegation:** in Antigravity or Claude Code you may hand steps 5–6 (render, verify) to the `video-editor` subagent.
- **Rules:** follow `AGENTS.md` (non-destructive, never blind center-crop, factual integrity, ethics and copyright flags).

## Setup

All scripts need only Python 3.8+ and ffmpeg. Set `S` to the `scripts/` folder next to this file:

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/video-to-social-content/scripts"   # Claude Code
# Codex / Antigravity: S="<path to this skill>/scripts"
```

Every script prints JSON and exits non-zero on failure; read the JSON instead of guessing.

## Step 0: Prepare

```bash
python3 "$S/prepare.py" "<video-or-url>" [--name <video-name>]
```

- Creates `outputs/<video-name>/` with `reels/`, `photos/`, `samples/` and writes `meta.json` (display size after rotation, duration, fps, audio). Local files are never copied or modified.
- For URLs it downloads `source.mp4` with yt-dlp (picking a JavaScript runtime automatically) and saves `source_info.json` (title, uploader, license) for attribution.
- Read `capabilities` in the output: if `transcription` or `face_detection` is `null`, those steps fall back to you (see Steps 1 and 3). If ffmpeg or yt-dlp is missing, offer to install it (`apt/brew/winget install ffmpeg`, `pipx install "yt-dlp[default]"`).
- If `reel_below_1080x1920` is true, remember to tell the user the final resolution (`reel_resolution`).

## Step 1: Analyze

```bash
python3 "$S/analyze.py" outputs/<video-name> [--model small] [--language en]
```

Writes `outputs/<video-name>/analysis/`:

| File | Use it to |
| :--- | :--- |
| `transcript.json` | Find quotes and sentence boundaries (word timestamps). Skipped if no Whisper is installed; offer `pip install faster-whisper`. |
| `candidates.json` | Start from ranked, sentence-aligned 15–60 s windows with reasons (speech, emphasis, loudness, scene activity). |
| `scenes.json`, `silences.json`, `loudness.json` | Check cut points and energy. |
| `sheets.json` + `samples/sheets/*.jpg` | See the video: each contact sheet shows up to 12 frames with their timestamps listed in `sheets.json`. |

Look at the contact sheets (not individual frames) to understand composition and where subjects sit. Without a transcript, rely on the sheets, scenes and loudness; say in the summary that speech recognition was skipped.

## Step 2: Select moments

- **Reels:** a hook in the first 2 seconds; a complete, self-contained beat; never cut mid-sentence, mid-word or mid-gesture (snap to transcript sentence ends or `silences.json`). Cover different genres in the video (action, insight, humor, emotion) rather than several similar clips. Treat `candidates.json` as a shortlist, not an answer.
- **Photos:** sharp, no motion blur, eyes open, flattering expression, good light. To choose between neighbouring frames, extract a few candidates into `samples/` and compare them.
- **Ethics:** apply `AGENTS.md` section 6 before choosing: no minors in sensitive contexts; tag mature or violent clips and suggest a cleaner cut.

## Step 3: Locate the subject

```bash
python3 "$S/track_subject.py" outputs/<video-name>/plan.json --write
```

Run it after drafting `plan.json` (Step 4). For each reel and photo without a subject position it detects faces and fills in `subject_x` (or `subject_track` when the subject moves), and flags clips it could not place or that should be split. It needs `opencv-python-headless`; if `face_detection` is `null`, read positions off the contact sheets yourself (sheet tiles are scaled; multiply by `scale` from `sheets.json`). **Never leave a landscape clip blind-centred** unless the subject really is centred.

## Step 4: Write and validate plan.json

Write `outputs/<video-name>/plan.json` (format and examples: `references/plan-format.md`), then:

```bash
python3 "$S/plan.py" outputs/<video-name>/plan.json
```

Fix every error; read the warnings.

## Step 5: Render

```bash
python3 "$S/render.py" outputs/<video-name>/plan.json --jobs 2
```

Renders every reel (`libx264` CRF 16 preset slow, yuv420p, AAC 192k, faststart, audio fades) and photo. Existing outputs are skipped; after changing the plan, use `--only <id> --force`. If the reels are below 1080x1920, tell the user and offer the blurred-background canvas (`"canvas": true`) or upscaling; render it only after they agree.

## Step 6: Verify

```bash
python3 "$S/verify.py" outputs/<video-name>/plan.json
```

Checks size, aspect ratio, codec, pixel format, duration, audio, faststart and blank frames for every output, and lists stale files. Then **look at every image in `review_images`** (start | mid | end per reel, plus photo sheets): subject framed, comfortable head room, nothing important cut off. Fix the plan and re-render until `ok` is true and the images look right.

## Step 7: Captions

```bash
python3 "$S/captions.py" scaffold outputs/<video-name>/plan.json
# fill in every TODO following references/captions.md
python3 "$S/captions.py" check outputs/<video-name>/plan.json
```

The scaffold pre-fills file links, timestamps, resolutions, transcript excerpts, the source attribution and the copyright reminder. Replace only the `TODO` markers, then run `check` until it passes.

## Step 8: Deliver

Reply with the Deliverables table from `captions.md` (links to every file), the output resolution (and the canvas/upscale offer if below 1080x1920), any content flags, and the copyright reminder for third-party footage. Mention anything that fell back to manual work (no transcript, no face detection).
