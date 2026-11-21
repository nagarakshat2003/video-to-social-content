---
name: video-to-social-content
description: Find the best moments from a video file or YouTube video and deliver 9:16 reel clips and 3:4 photos cropped from the source, with social media captions.
---

# Video to Social Content

Processes video files or YouTube URLs into viral-ready vertical 9:16 reels and 3:4 photo carousels, paired with high-converting social media captions and metadata.

## Trigger & Scope

- **Invocation:** Triggered via the `/video-to-social-content` slash command or whenever a user asks to convert, slice, or extract reels, shorts, or stills from a video.
- **Inputs:** Local video file path (e.g., `.mp4`, `.mov`, `.mkv`) or YouTube URL. Any accompanying prompt instructions (focus, genre preferences, platform, tone, clip count) override defaults.
- **Default Targets:**
  - **Reels:** 3–6 vertical clips (15–60 seconds, hard cap 90s).
  - **Photos:** 6–10 stills grouped into 1–3 carousel posts (3–4 photos per post).
  - **Captions:** Comprehensive `captions.md` file saved alongside media, plus an interactive summary table in chat.

---

## Step 0: Tooling & Preflight Checks

Run preflight checks using `run_command` in PowerShell or Bash:

1. **Verify ffmpeg & ffprobe:**
   ```powershell
   ffmpeg -version; ffprobe -version
   ```
   *If missing:* Offer to install via `winget install Gyan.FFmpeg` or `choco install ffmpeg` on Windows, or use `python -m pip install imageio-ffmpeg`.
2. **Verify Whisper / Audio transcription (optional but recommended):**
   ```powershell
   python -c "import whisper; print('Whisper ready')" 2>$null || python -c "import faster_whisper; print('Faster-Whisper ready')" 2>$null
   ```
   *If unavailable:* Proceed with visual inspection and embedded subtitles/audio waveform analysis, noting that automatic speech recognition was skipped.
3. **Workspace Isolation:**
   Create output directories under `outputs/<video-basename>/`:
   ```powershell
   New-Item -ItemType Directory -Force -Path "outputs/<video-name>/reels", "outputs/<video-name>/photos"
   ```

---

## Step 1: Inspect Video & Build Evidence

Never work blindly on the video. Gather concrete metrics and sample evidence:

1. **Inspect Metadata with `ffprobe`:**
   ```powershell
   ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,duration,codec_name -of json "source.mp4"
   ```
   Extract width ($W$), height ($H$), duration ($T$), frame rate, and rotation metadata.

2. **Transcribe Audio:**
   Extract dialogue using Whisper or an audio-to-text script. Note exact timestamp intervals for high-energy dialogue, quotes, jokes, or emotional exchanges.

3. **Detect Scene Changes & Sample Frames:**
   Extract candidate scene cuts:
   ```powershell
   ffmpeg -i "source.mp4" -vf "select='gt(scene,0.3)',showinfo" -f null - 2> scenes.log
   ```
   Sample periodic frames (1 frame per 2–3s for short videos, 1 per 5–10s for longer footage):
   ```powershell
   ffmpeg -i "source.mp4" -vf "fps=1/3" -q:v 2 "outputs/<video-name>/samples/frame_%04d.jpg"
   ```
   Generate a contact sheet or inspect candidate keyframes with `read_file` to visually verify camera composition and subject placement.

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
  ```powershell
  ffmpeg -ss 00:01:24.500 -i "source.mp4" -vframes 5 "candidate_%02d.png"
  ```
- Group selected photos into 1–3 cohesive carousel sets (e.g., 3–4 photos per theme).

---

## Step 3: Subject-Aware Cropping (Never Blind Center-Crop)

Never squash, stretch, or default to center-cropping.

### Crop Mathematics (Landscape Source $W \times H$)
1. **9:16 Vertical Reel Crop:**
   - Crop height = source height $H$.
   - Target width: $w_{9:16} = \lfloor H \times 9 / 16 \rfloor$. Ensure $w_{9:16}$ is an even integer:
     $$w = 2 \times \lfloor w_{9:16} / 2 \rfloor$$
2. **3:4 Photo Crop:**
   - Crop height = source height $H$.
   - Target width: $w_{3:4} = \lfloor H \times 3 / 4 \rfloor$. Ensure $w_{3:4}$ is an even integer:
     $$w = 2 \times \lfloor w_{3:4} / 2 \rfloor$$

### Determining Horizontal Offset ($x$)
- Inspect sampled frames during the clip's timestamp range.
- Locate the primary subject (speaker's face or central action) at coordinate $X_{subject}$.
- Set $x = \text{clamp}(X_{subject} - w / 2, 0, W - w)$.
- If the subject moves significantly across the clip, either split the moment into two cuts or apply a smooth crop pan.

### FFmpeg Rendering Commands

- **Render Reel:**
  ```powershell
  ffmpeg -ss <start_time> -to <end_time> -i "source.mp4" `
    -vf "crop=<w>:<h>:<x>:0,afade=t=in:ss=0:d=0.3,afade=t=out:st=<duration_minus_0.5>:d=0.5" `
    -c:v libx264 -crf 16 -preset slow -c:a aac -b:a 192k -movflags +faststart `
    "outputs/<video-name>/reels/reel_01_<genre>.mp4"
  ```
- **Extract & Crop Photo:**
  ```powershell
  ffmpeg -ss <timestamp> -i "source.mp4" -vframes 1 `
    -vf "crop=<w>:<h>:<x>:0" -q:v 1 `
    "outputs/<video-name>/photos/photo_01_<theme>.jpg"
  ```

### Resolution Reporting Rule
- Report the final output resolution (e.g. $608 \times 1080$).
- If less than $1080 \times 1920$, notify the user and offer an optional blurred-background 1080x1920 canvas fit as a next step.

---

## Step 4: Verify Every Output

Before presenting deliverables to the user:
1. Run `ffprobe` on each generated reel and photo to verify dimensions, aspect ratio, frame rate, and audio stream.
2. Extract the first, middle, and last frame of each reel:
   ```powershell
   ffmpeg -ss <start> -i reel.mp4 -vframes 1 frame_start.jpg
   ffmpeg -ss <mid> -i reel.mp4 -vframes 1 frame_mid.jpg
   ffmpeg -ss <end> -i reel.mp4 -vframes 1 frame_end.jpg
   ```
3. Inspect the images using `read_file` to ensure subjects are centered, head room is comfortable, and text/captions won't obstruct facial features.

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
| [reel_01_insight.mp4](file:///C:/path/to/outputs/.../reels/reel_01_insight.mp4) | 9:16 Reel | 01:14 - 01:45 | Drama / Insight | "The $2M Mistake" |
| [photo_01_speaker.jpg](file:///C:/path/to/outputs/.../photos/photo_01_speaker.jpg) | 3:4 Stills | 01:24 | Carousel 1 (1/3) | Keynote reaction |

3. Include any required sensitive content warnings (violence/mature tags) or copyright notes.
