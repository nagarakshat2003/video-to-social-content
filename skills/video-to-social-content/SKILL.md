---
name: video-to-social-content
description: Find the best moments from a video file or YouTube video and deliver 9:16 reel clips and 3:4 photos cropped from the source, with social media captions.
---

# Video to Social Content

Processes video files or YouTube URLs into viral-ready vertical 9:16 reels and 3:4 photo carousels, paired with high-converting social media captions and metadata.

## Trigger & Scope

- **Invocation:** Triggered via the `/video-to-social-content` slash command, `$video-to-social-content`, or whenever a user asks to convert, slice, or extract reels, shorts, or stills from a video.
- **Inputs:** Local video file path (e.g., `.mp4`, `.mov`, `.mkv`) or YouTube URL. Any accompanying prompt instructions (focus, genre preferences, platform, tone, clip count) override defaults.
- **Execution Mode:**
  - **Single-Agent (Codex / Direct):** The primary agent executes the steps below sequentially using shell and file tools.
  - **Subagent Delegation (Antigravity / Claude Code):** The coordinator may delegate slicing and verification to the `video-editor` subagent.
- **Default Targets:**
  - **Reels:** 3–6 vertical clips (15–60 seconds, hard cap 90s).
  - **Photos:** 6–10 stills grouped into 1–3 carousel posts (3–4 photos per post).
  - **Captions:** Comprehensive `captions.md` file saved alongside media, plus an interactive summary table in chat.

---

## Step 0: Tooling & Preflight Checks

Run preflight checks using your environment's shell command tool (`run_command`, `Bash`, or native CLI):

1. **Verify ffmpeg & ffprobe:**
   ```bash
   ffmpeg -version && ffprobe -version
   ```
   *If missing:* Offer to install via package manager (`sudo apt-get install ffmpeg`, `brew install ffmpeg`, or `winget install Gyan.FFmpeg`).
2. **Verify yt-dlp (URL inputs only):**
   ```bash
   yt-dlp --version
   deno --version || node --version
   ```
   *If missing:* Offer to install it with its YouTube challenge solver (`pipx install "yt-dlp[default]"`, `pip install -U "yt-dlp[default]"`, or `brew install yt-dlp`), or ask the user for a local copy of the video. Distro packages (e.g. `apt install yt-dlp`) are usually too old for YouTube.
   YouTube also requires a JavaScript runtime. yt-dlp uses Deno by default; if only Node.js is available, add `--js-runtimes node` to the download command. Without a runtime and solver, yt-dlp warns "n challenge solving failed" and formats may be missing.
3. **Verify Whisper / Audio transcription (optional but recommended):**
   ```bash
   python3 -c "import whisper; print('Whisper ready')" 2>/dev/null || python3 -c "import faster_whisper; print('Faster-Whisper ready')" 2>/dev/null || echo "Whisper not installed"
   ```
   *If unavailable:* Proceed with visual sampling and embedded subtitles/audio waveform analysis, noting that automatic speech recognition was skipped.
4. **Workspace Isolation:**
   Create output directories under `outputs/<video-name>/`:
   ```bash
   mkdir -p "outputs/<video-name>/reels" "outputs/<video-name>/photos" "outputs/<video-name>/samples"
   ```
5. **Fetch URL Inputs:**
   If the input is a YouTube (or other supported) URL, download it into the workspace and use the downloaded file as `source.mp4` for every later step:
   ```bash
   yt-dlp -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b" --merge-output-format mp4 \
     -o "outputs/<video-name>/source.%(ext)s" "<URL>"
   ```
   Add `--js-runtimes node` when Deno is not installed. YouTube may serve AV1 video; that is fine, since every render re-encodes to H.264.
   Third-party footage triggers the copyright reminder in the deliverables (see `AGENTS.md`, section 6).

---

## Step 1: Inspect Video & Build Evidence

Never work blindly on the video. Gather concrete metrics and sample evidence:

1. **Inspect Metadata with `ffprobe`:**
   ```bash
   ffprobe -v error -select_streams v:0 \
     -show_entries stream=width,height,r_frame_rate,codec_name:stream_side_data=rotation:format=duration \
     -of json "source.mp4"
   ```
   Extract width ($W$), height ($H$), duration ($T$, from `format.duration`, which is present even when the stream has none, e.g. MKV/WebM), frame rate, and rotation.
   - **Rotation:** If `side_data_list` reports `rotation` of `90`, `-90`, or `270` (typical for phone footage), ffmpeg auto-rotates frames on decode, so swap the values: use $W$ = reported height and $H$ = reported width for all crop math and filters.

2. **Transcribe Audio:**
   Extract dialogue using Whisper or an audio-to-text script. Note exact timestamp intervals for high-energy dialogue, quotes, jokes, or emotional exchanges.

3. **Detect Scene Changes & Sample Frames:**
   Extract candidate scene cuts:
   ```bash
   ffmpeg -i "source.mp4" -vf "select='gt(scene,0.3)',showinfo" -f null - 2> "outputs/<video-name>/samples/scenes.log"
   ```
   Sample periodic frames (1 frame per 2–3s for short videos, 1 per 5–10s for longer footage):
   ```bash
   ffmpeg -i "source.mp4" -vf "fps=1/3" -q:v 2 "outputs/<video-name>/samples/frame_%04d.jpg"
   ```
   Inspect candidate keyframes with your file viewer / image tool (`read_file`, `Read`, or visual inspector) to visually verify camera composition and subject placement.

4. **Construct the Timeline:**
   Build an internal timeline table:
   | Start - End | Description / Action | Dialogue Highlight | Genre / Vibe | Hook Strength (1-10) |
   | :--- | :--- | :--- | :--- | :--- |
   | `00:01:14 - 00:01:48` | Heated debate on startup failure | "We lost $2M in 48 hours..." | Drama / Insight | 9/10 |

---

## Step 2: Select Moments

### A. Reels (15–60 seconds, max 90s)
- **Hook in first 2 seconds:** The opening must immediately grab attention (striking statement, dramatic sound, sudden motion, or question).
- **Self-contained narrative beat:** A complete mini-story or point. Do not cut off mid-sentence, mid-word, or mid-gesture.
- **Genre Diversity:** Prioritize covering diverse genres present in the video (e.g. 1 Action/High Energy, 1 Insight/Deep Conversation, 1 Comedy/Humorous beat, 1 Emotional moment) rather than 5 identical clips.

### B. Photos (3:4 ratio stills)
- **Quality criteria:** Sharp focus, no motion blur, no half-closed eyes or mid-speech mouth shapes, excellent lighting, expressive facial expressions.
- Extract 3–5 neighboring candidate frames around the key moment and inspect them to select the single best still:
  ```bash
  ffmpeg -ss 00:01:24.500 -i "source.mp4" -vframes 5 "outputs/<video-name>/samples/candidate_%02d.png"
  ```
- Group selected photos into 1–3 cohesive carousel sets (e.g., 3–4 photos per theme).

---

## Step 3: Subject-Aware Cropping (Never Blind Center-Crop)

Never squash, stretch, or default to center-cropping.

### Crop Calculation with `crop_math.py`
Use the bundled `crop_math.py` script to calculate exact bounds and offsets:
```bash
python3 "${CLAUDE_PLUGIN_ROOT:-.}/skills/video-to-social-content/scripts/crop_math.py" \
  --width <W> --height <H> --ratio 9:16 --subject-x <X_subject>
```

### Crop Mathematics (Landscape Source $W \times H$)
1. **9:16 Vertical Reel Crop:**
   - Crop height = source height $H$.
   - Target width: $w_{9:16} = \lfloor H \times 9 / 16 \rfloor$. Ensure $w_{9:16}$ is an even integer:
     $$w = 2 \times \lfloor w_{9:16} / 2 \rfloor$$
2. **3:4 Photo Crop:**
   - Crop height = source height $H$.
   - Target width: $w_{3:4} = \lfloor H \times 3 / 4 \rfloor$. Ensure $w_{3:4}$ is an even integer:
     $$w = 2 \times \lfloor w_{3:4} / 2 \rfloor$$
3. **Sources Narrower Than the Target** (e.g. a 4:5 portrait clip going to 9:16, or 9:16 footage going to 3:4):
   - Crop width = source width $W$; crop height = $W \times 16 / 9$ (9:16) or $W \times 4 / 3$ (3:4), rounded down to an even integer.
   - Set $y = \text{clamp}(Y_{subject} - h / 2, 0, H - h)$ and $x = 0$.
   - `crop_math.py` makes this choice automatically: it compares $W/H$ against the target ratio and crops whichever dimension overflows, so the crop never exceeds the source frame. Pass `--subject-y` to place the vertical offset.

### Determining Horizontal Offset ($x$)
- Inspect sampled frames during the clip's timestamp range.
- Locate the primary subject (speaker's face or central action) at coordinate $X_{subject}$.
- Set $x = \text{clamp}(X_{subject} - w / 2, 0, W - w)$.
- If the subject moves significantly across the clip, either split the moment into two cuts or apply a smooth crop pan.

### FFmpeg Rendering Commands

- **Render Reel:**
  ```bash
  ffmpeg -ss <start_time> -i "source.mp4" -t <duration> \
    -vf "crop=<w>:<h>:<x>:<y>" \
    -af "afade=t=in:st=0:d=0.3,afade=t=out:st=<duration_minus_0.5>:d=0.5" \
    -c:v libx264 -crf 16 -preset slow -c:a aac -b:a 192k -movflags +faststart \
    "outputs/<video-name>/reels/reel_01_<genre>.mp4"
  ```
  Video filters go in `-vf` and audio fades in `-af`; mixing them in one `-vf` chain makes ffmpeg fail with "Media type mismatch". Fade timestamps are relative to the clip start, so `<duration_minus_0.5>` is the clip length minus 0.5s.
- **Extract & Crop Photo:**
  ```bash
  ffmpeg -ss <timestamp> -i "source.mp4" -vframes 1 \
    -vf "crop=<w>:<h>:<x>:<y>" -q:v 1 \
    "outputs/<video-name>/photos/photo_01_<theme>.jpg"
  ```

### Resolution Reporting Rule
- Report the final output resolution (e.g. $608 \times 1080$).
- If less than $1080 \times 1920$, notify the user and offer an optional blurred-background 1080x1920 canvas fit as a next step. Only run it after the user agrees; the reel itself stays at native size, centered on a blurred fill:
  ```bash
  ffmpeg -i "outputs/<video-name>/reels/reel_01_<genre>.mp4" \
    -filter_complex "[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:20[bg];[bg][b]overlay=(W-w)/2:(H-h)/2" \
    -c:v libx264 -crf 16 -preset slow -c:a copy -movflags +faststart \
    "outputs/<video-name>/reels/reel_01_<genre>_1080x1920.mp4"
  ```

---

## Step 4: Verify Every Output

Before presenting deliverables to the user:
1. Run `ffprobe` on each generated reel and photo to verify dimensions, aspect ratio, frame rate, and audio stream.
2. Extract the first, middle, and last frame of each reel:
   ```bash
   ffmpeg -i reel.mp4 -vframes 1 "outputs/<video-name>/samples/frame_start.jpg"
   ffmpeg -ss <duration_divided_by_2> -i reel.mp4 -vframes 1 "outputs/<video-name>/samples/frame_mid.jpg"
   ffmpeg -sseof -0.1 -i reel.mp4 -vframes 1 "outputs/<video-name>/samples/frame_end.jpg"
   ```
   Use `-sseof` for the end frame: seeking to exactly the clip duration returns no frame.
3. Visually inspect the images to ensure subjects are centered, head room is comfortable, and on-screen graphics won't obstruct facial features.

---

## Step 5: Craft Captions & Format Deliverables

### Caption Guidelines
- **Reels Captions:**
  - Punchy hook opening line (stops the scroll).
  - 1–3 context/storytelling sentences matching the tone of the video.
  - Call to Action (CTA) (e.g., "Which moment was your favorite? Comment below 👇").
  - 3–5 relevant, high-traffic hashtags.
  - Short on-screen text suggestion (e.g., *[On-screen text: "When you realize you forgot to commit..."]*).
- **Photo Carousel Captions:**
  - 80–200 words of rich storytelling explaining the moment, mood, or insight.
  - Specified carousel display order (Slide 1, Slide 2, Slide 3...).
  - Engaging reflection or question + hashtags.
- **Authenticity Rule:** Use only verifiable dialogue and facts from the footage. Never invent names, quotes, or statistics.

### Deliverables Output
1. Write the full formatted caption document to `outputs/<video-name>/captions.md`.
2. Present a clear summary table in chat with clickable file links:

| Output File | Type | Timestamp Range | Genre / Theme | Key Hook / Headline |
| :--- | :--- | :--- | :--- | :--- |
| [reel_01_insight.mp4](file:///path/to/outputs/.../reels/reel_01_insight.mp4) | 9:16 Reel | 01:14 - 01:45 | Drama / Insight | "The $2M Mistake" |
| [photo_01_speaker.jpg](file:///path/to/outputs/.../photos/photo_01_speaker.jpg) | 3:4 Stills | 01:24 | Carousel 1 (1/3) | Keynote reaction |

3. Include any required sensitive content warnings (violence/mature tags) or copyright notes.
