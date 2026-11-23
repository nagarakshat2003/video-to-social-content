#!/usr/bin/env bash
# 40 s 1280x720 clip: two visual scenes, speech-like tone bursts with a pause, loud final section.
set -euo pipefail
ffmpeg -hide_banner -v error -y \
  -f lavfi -i "testsrc2=s=1280x720:r=30:d=20" -f lavfi -i "smptehdbars=s=1280x720:r=30:d=20" \
  -f lavfi -i "sine=f=220:d=20,volume=0.3,apad=whole_dur=20" \
  -f lavfi -i "sine=f=440:d=20,volume=0.9" \
  -filter_complex "[0:v][2:a][1:v][3:a]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" \
  -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac interview.mp4
