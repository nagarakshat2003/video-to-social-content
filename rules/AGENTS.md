# Video to Social Content Rules

These rules apply whenever handling video processing, cropping, and social media content generation.

## 1. Non-Destructive Operations
- **Never modify the original video source file.** Always read from the source and output generated clips and stills into a dedicated working directory: `outputs/<video-name>/reels/` and `outputs/<video-name>/photos/`.
- If working with multiple videos in one session, isolate each video into its own distinct subfolder under `outputs/<video-name>/`.

## 2. Subject-Aware Cropping (Never Blind Center-Crop)
- **Crop, do not stretch, squash, or letterbox.**
- For landscape footage: keep source height $h$ and compute target width:
  - **9:16 Vertical Reels:** $w = \lfloor h \times 9 / 16 \rfloor$ (rounded down to even numbers).
  - **3:4 Portrait Photos:** $w = \lfloor h \times 3 / 4 \rfloor$ (rounded down to even numbers).
- If source is portrait or narrower than target ratio, crop height instead.
- **Inspect Subject Offset:** Determine the crop x-offset ($x$) by analyzing sampled frames (tracking faces, speakers, or primary action). If the subject shifts horizontally across the clip, either split the moment into two cuts or apply a pan/tracked crop.
- Never blindly assume $x = (W - w) / 2$.

## 3. Resolution & Quality Integrity
- **No silent upscaling:** Keep native source pixel density.
- Always report the final output resolution.
- If final 9:16 reel resolution is below 1080x1920 (e.g. source was 1080p landscape yielding a ~608x1080 crop), explicitly inform the user and offer blurred-background canvas fitting (`split [a][b]; [a] scale=1080:1920:force_original_aspect_ratio=increase,boxblur=20:20 [bg]; [bg][b] overlay=(W-w)/2:(H-h)/2`) or upscaling as an optional next step.
- Reel encoding standard: `libx264`, `-crf 16`, `-preset slow`, `aac`, `-movflags +faststart`, with short audio fades (`afade=t=in...`, `afade=t=out...`).
- Photo extraction standard: PNG or high-quality JPEG (`-q:v 1`).

## 4. Rigorous Output Verification
- Every generated reel and photo must be verified before presenting to the user:
  - Check dimensions, aspect ratio, duration, and audio stream presence with `ffprobe`.
  - Extract the first, middle, and last frame of each reel and inspect them with `read_file` to confirm framing and head room.
  - Inspect each candidate photo for sharpness, lighting, open eyes, and absence of motion blur.

## 5. Factual Accuracy & Attribution
- **Never invent dialogue, facts, speaker identities, quotes, or locations** that are not explicitly audible, visible, or provided in user instructions.
- If dialogue is muffled, unclear, or a speaker is unknown, use descriptive or generic references rather than guessing.

## 6. Content Ethics, Safety & Copyright Flags
- **Minors:** Never clip, capture, or caption anyone who appears to be a minor in sexual, sensitive, or suggestive contexts.
- **Sensitive Genres:** When violence or adult themes are detected and clipped, explicitly tag the clip (e.g., `[Mature / Violence]`), warn the user of platform restriction/demonetization risks on Instagram, TikTok, and YouTube, and suggest a cleaner alternative cut point.
- **Copyright Disclaimers:** When footage originates from films, television broadcasts, or third-party creators, include a standard reminder that public posting may incur DMCA takedowns or copyright claims unless licensed.
- **Real People:** Captions must never assert speculative claims or defamatory statements about identifiable real individuals beyond what is directly shown in the footage.
