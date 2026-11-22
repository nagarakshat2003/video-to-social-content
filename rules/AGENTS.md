# Video to Social Content Rules

These rules apply whenever handling video processing, cropping, and social media content generation. The workflow and the scripts that enforce most of these rules are in `skills/video-to-social-content/SKILL.md`.

## 1. Non-Destructive Operations
- **Never modify the original video source file.** Always read from the source and output generated clips and stills into a dedicated working directory: `outputs/<video-name>/reels/` and `outputs/<video-name>/photos/`.
- If working with multiple videos in one session, isolate each video into its own distinct subfolder under `outputs/<video-name>/`.

## 2. Subject-Aware Cropping (Never Blind Center-Crop)
- **Crop, do not stretch, squash, or letterbox.**
- For landscape footage: keep source height $h$ and compute target width:
  - **9:16 Vertical Reels:** $w = \lfloor h \times 9 / 16 \rfloor$ (rounded down to even numbers).
  - **3:4 Portrait Photos:** $w = \lfloor h \times 3 / 4 \rfloor$ (rounded down to even numbers).
- If source is portrait or narrower than target ratio, crop height instead.
- **Inspect Subject Offset:** Determine the subject position from sampled frames (faces, speakers, or primary action), with `track_subject.py` when available, and record it in `plan.json` (`subject_x`, `subject_y`, or `subject_track`). If the subject shifts across the clip, either split the moment into two cuts or use a tracked pan (`subject_track`).
- Never blindly assume $x = (W - w) / 2$. Crop bounds and offsets are computed by the scripts (`render.py` via `crop_math.py`); never hand-calculate them.

## 3. Resolution & Quality Integrity
- **No silent upscaling:** Keep native source pixel density.
- Always report the final output resolution.
- If final 9:16 reel resolution is below 1080x1920 (e.g. source was 1080p landscape yielding a ~608x1080 crop), explicitly inform the user and offer blurred-background canvas fitting (`"canvas": true` in `plan.json`, rendered by `render.py`) or upscaling as an optional next step. Render either only after the user agrees.
- Reel encoding standard (built into `render.py`): `libx264`, `-crf 16`, `-preset slow`, `yuv420p`, `aac` 192k, `-movflags +faststart`, with short audio fades applied through `-af`, never inside the `-vf` video chain.
- Photo extraction standard: PNG or high-quality JPEG (`-q:v 1`).

## 4. Rigorous Output Verification
- Every generated reel and photo must be verified before presenting to the user:
  - Run `verify.py`: it checks dimensions, aspect ratio, codec, duration, audio presence and faststart, and builds start/mid/end review sheets. It must report `ok`.
  - Visually inspect every review image it lists with your image viewer (`Read`, `read_file`, or equivalent) to confirm framing and head room.
  - Inspect each candidate photo for sharpness, lighting, open eyes, and absence of motion blur.

## 5. Factual Accuracy & Attribution
- **Never invent dialogue, facts, speaker identities, quotes, or locations** that are not explicitly audible, visible, or provided in user instructions. Quote only from the transcript (or clearly audible speech).
- If dialogue is muffled, unclear, or a speaker is unknown, use descriptive or generic references rather than guessing.

## 6. Content Ethics, Safety & Copyright Flags
- **Minors:** Never clip, capture, or caption anyone who appears to be a minor in sexual, sensitive, or suggestive contexts.
- **Sensitive Genres:** When violence or adult themes are detected and clipped, explicitly tag the clip (e.g., `[Mature / Violence]`), warn the user of platform restriction/demonetization risks on Instagram, TikTok, and YouTube, and suggest a cleaner alternative cut point.
- **Copyright Disclaimers:** When footage originates from films, television broadcasts, or third-party creators, include a standard reminder that public posting may incur DMCA takedowns or copyright claims unless licensed.
- **Real People:** Captions must never assert speculative claims or defamatory statements about identifiable real individuals beyond what is directly shown in the footage.
