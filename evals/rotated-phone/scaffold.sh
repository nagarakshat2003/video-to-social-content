#!/usr/bin/env bash
# Phone-style clip: coded 1920x1080 with 90-degree rotation metadata, so it displays as 1080x1920.
set -euo pipefail
ffmpeg -hide_banner -v error -y -f lavfi -i "testsrc2=s=1920x1080:r=30:d=25" -f lavfi -i "sine=f=330:d=25" \
  -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac flat.mp4
if ffmpeg -hide_banner -h full 2>/dev/null | grep -q -- "-display_rotation"; then
  ffmpeg -hide_banner -v error -y -display_rotation 90 -i flat.mp4 -c copy phone.mp4
else  # ffmpeg < 6 stores rotation as a stream tag
  ffmpeg -hide_banner -v error -y -i flat.mp4 -c copy -metadata:s:v:0 rotate=90 phone.mp4
fi
rm flat.mp4
