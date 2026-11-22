#!/usr/bin/env python3
"""
prepare.py - Step 0 + 1 in one command: preflight, fetch, workspace, probe.

- Local file: never copied or modified; its absolute path is recorded.
- URL: downloaded with yt-dlp to outputs/<name>/source.mp4, with title,
  uploader and license saved to source_info.json (used for attribution and
  copyright reminders).
- Creates outputs/<name>/{reels,photos,samples} and writes meta.json.
- Reports which optional capabilities are installed (transcription, face
  detection) so the agent knows which steps it must do by hand.

Usage:
  prepare.py <video-or-url> [--name NAME] [--outputs outputs]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from crop_math import calculate_crop
from common import ToolError, Workspace, emit, fail, read_json, require, run, slugify, write_json
from probe import probe

URL_RE = re.compile(r"^https?://", re.I)
FORMAT_SELECTOR = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b"
YTDLP_HINT = 'Install it with: pipx install "yt-dlp[default]" (or pip install -U "yt-dlp[default]", brew install yt-dlp).'


def js_runtime_args() -> List[str]:
    """yt-dlp uses Deno by default for YouTube; fall back to Node or Bun."""
    if shutil.which("deno"):
        return []
    for runtime in ("node", "bun"):
        if shutil.which(runtime):
            return ["--js-runtimes", runtime]
    return []


def capabilities() -> Dict[str, Any]:
    def has(mod: str) -> bool:
        return importlib.util.find_spec(mod) is not None

    return {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "yt_dlp": bool(shutil.which("yt-dlp")),
        "js_runtime": next((r for r in ("deno", "node", "bun") if shutil.which(r)), None),
        "transcription": "faster_whisper" if has("faster_whisper") else ("whisper" if has("whisper") else None),
        "face_detection": "opencv" if has("cv2") else None,
    }


def fetch_info(url: str) -> Dict[str, Any]:
    ytdlp = require("yt-dlp", YTDLP_HINT)
    proc = run([ytdlp, *js_runtime_args(), "--skip-download", "--no-playlist", "-J", url])
    info = json.loads(proc.stdout)
    return {
        "url": url,
        "id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader") or info.get("channel"),
        "channel_url": info.get("channel_url") or info.get("uploader_url"),
        "license": info.get("license"),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "extractor": info.get("extractor_key"),
    }


def download(url: str, ws: Workspace) -> Path:
    ytdlp = require("yt-dlp", YTDLP_HINT)
    existing = ws.root / "source.mp4"
    if existing.is_file():
        return existing
    run([
        ytdlp, *js_runtime_args(), "--no-playlist", "--no-progress",
        "-f", FORMAT_SELECTOR, "--merge-output-format", "mp4",
        "-o", str(ws.root / "source.%(ext)s"), url,
    ])
    if not existing.is_file():
        found = sorted(ws.root.glob("source.*"))
        if not found:
            raise ToolError("yt-dlp finished but no source file was written.")
        return found[0]
    return existing


def prepare(target: str, name: Optional[str], outputs: Path) -> Dict[str, Any]:
    require("ffmpeg", "Install ffmpeg: apt install ffmpeg / brew install ffmpeg / winget install Gyan.FFmpeg")
    info = None
    if URL_RE.match(target):
        info = fetch_info(target)
        name = name or slugify(info.get("title") or info.get("id") or "video")
        ws = Workspace(outputs / name).create()
        write_json(ws.source_info, info)
        source = download(target, ws)
    else:
        source = Path(target)
        if not source.is_file():
            raise ToolError(f"Video not found: {target}")
        name = name or slugify(source.stem)
        ws = Workspace(outputs / name).create()
        if ws.source_info.is_file():
            info = read_json(ws.source_info)

    meta = probe(str(source))
    meta["name"] = name
    write_json(ws.meta, meta)
    reel = calculate_crop(meta["width"], meta["height"], "9:16")
    return {
        "workspace": str(ws.root),
        "meta": meta,
        "source_info": info,
        "capabilities": capabilities(),
        "reel_resolution": reel["resolution"],
        "reel_below_1080x1920": reel["crop_w"] < 1080 or reel["crop_h"] < 1920,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", help="Local video path or URL")
    parser.add_argument("--name", help="Workspace name (default: slug of the file name or video title)")
    parser.add_argument("--outputs", type=Path, default=Path("outputs"), help="Outputs root (default: outputs)")
    args = parser.parse_args()
    try:
        result = prepare(args.target, args.name, args.outputs)
    except ToolError as exc:
        fail(str(exc))
    emit(result)


if __name__ == "__main__":
    main()
