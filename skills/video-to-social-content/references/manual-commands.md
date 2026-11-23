# Manual Commands (Fallback Only)

Use these only when the bundled scripts cannot run (no Python 3.8+). They are the same commands the scripts build, so the house standards still apply. Replace every `<placeholder>`.

## Probe

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate,codec_name:stream_side_data=rotation:format=duration \
  -of json "source.mp4"
```

- Duration comes from `format.duration` (present even for MKV/WebM).
- If `side_data_list` reports `rotation` of `90`, `-90` or `270`, ffmpeg auto-rotates on decode: use $W$ = reported height and $H$ = reported width.

## Download a URL

```bash
yt-dlp -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b" --merge-output-format mp4 \
  -o "outputs/<video-name>/source.%(ext)s" "<URL>"
```

YouTube needs a JavaScript runtime: Deno is used by default; add `--js-runtimes node` when only Node.js is installed.

## Crop size

- Source wider than the target ratio: crop height $h = H$ (even), width $w = \lfloor h \times r_w / r_h \rfloor$ rounded down to even, $x = \text{clamp}(X_{subject} - w/2, 0, W - w)$, $y = 0$.
- Source narrower than the target: crop width $w = W$ (even), height $h = \lfloor w \times r_h / r_w \rfloor$ rounded down to even, $y = \text{clamp}(Y_{subject} - h/2, 0, H - h)$, $x = 0$.
- `crop_math.py` (no dependencies besides Python) computes this: `python3 crop_math.py -W <W> -H <H> -r 9:16 -x <X>`.

## Render a reel

```bash
ffmpeg -ss <start> -i "source.mp4" -t <duration> -map 0:v:0 -map 0:a:0 \
  -vf "crop=<w>:<h>:<x>:<y>" \
  -af "afade=t=in:st=0:d=0.3,afade=t=out:st=<duration_minus_0.5>:d=0.5" \
  -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart \
  "outputs/<video-name>/reels/reel_<id>_<slug>.mp4"
```

Audio fades must be in `-af`; putting them in the `-vf` chain fails with "Media type mismatch". Drop `-map 0:a:0`, `-af` and the audio codec options when the source has no audio.

## Extract a photo

```bash
ffmpeg -ss <time> -i "source.mp4" -frames:v 1 -vf "crop=<w>:<h>:<x>:<y>" -q:v 1 \
  "outputs/<video-name>/photos/photo_<id>_<slug>.jpg"
```

## Blurred-background 1080x1920 canvas (only after the user agrees)

```bash
ffmpeg -i "outputs/<video-name>/reels/reel_<id>_<slug>.mp4" \
  -filter_complex "[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:20[bg];[bg][b]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]" \
  -map "[v]" -map 0:a:0 -c:v libx264 -crf 16 -preset slow -c:a copy -movflags +faststart \
  "outputs/<video-name>/reels/reel_<id>_<slug>_1080x1920.mp4"
```

## Verify

```bash
ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,pix_fmt:format=duration -of compact "<reel>.mp4"
ffmpeg -i "<reel>.mp4" -frames:v 1 "outputs/<video-name>/samples/verify/<reel>_start.jpg"
ffmpeg -ss <duration_divided_by_2> -i "<reel>.mp4" -frames:v 1 "outputs/<video-name>/samples/verify/<reel>_mid.jpg"
ffmpeg -sseof -0.1 -i "<reel>.mp4" -frames:v 1 "outputs/<video-name>/samples/verify/<reel>_end.jpg"
```

Seeking to exactly the clip duration returns no frame; use `-sseof` for the end frame.

## Scene changes and sample frames

```bash
ffmpeg -i "source.mp4" -vf "select='gt(scene,0.3)',showinfo" -f null - 2> "outputs/<video-name>/samples/scenes.log"
ffmpeg -i "source.mp4" -vf "fps=1/3,scale=-2:360,tile=4x3" "outputs/<video-name>/samples/sheet_%03d.jpg"
```
