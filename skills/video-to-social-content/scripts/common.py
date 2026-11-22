"""
common.py - Shared helpers for the video-to-social-content scripts.

Standard library only (Python 3.8+), so every script runs wherever the agent runs.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# Encoding standard shared by render.py and verify.py (see AGENTS.md section 3).
VIDEO_CODEC = "libx264"
VIDEO_CRF = "16"
VIDEO_PRESET = "slow"
PIX_FMT = "yuv420p"
AUDIO_CODEC = "aac"
AUDIO_BITRATE = "192k"
CANVAS_W, CANVAS_H = 1080, 1920

REEL_MIN_S, REEL_MAX_S = 3.0, 90.0          # hard limits
REEL_SOFT_MIN_S, REEL_SOFT_MAX_S = 15.0, 60.0  # recommended range


class ToolError(RuntimeError):
    """A required external tool is missing or a command failed."""


def require(tool: str, hint: str = "") -> str:
    path = shutil.which(tool)
    if not path:
        msg = f"'{tool}' was not found on PATH."
        if hint:
            msg += f" {hint}"
        raise ToolError(msg)
    return path


def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace"
    )
    if check and proc.returncode != 0:
        tail = proc.stderr.strip()[-2000:]
        raise ToolError(f"Command failed ({proc.returncode}): {shlex.join(cmd)}\n{tail}")
    return proc


_FFMPEG_MAJOR: Dict[str, int] = {}


def ffmpeg_major(ffmpeg: str = "ffmpeg") -> int:
    """Major version of ffmpeg (git/nightly builds count as new)."""
    if ffmpeg not in _FFMPEG_MAJOR:
        out = run([ffmpeg, "-hide_banner", "-version"], check=False).stdout
        m = re.search(r"version\s+n?(\d+)\.", out)
        _FFMPEG_MAJOR[ffmpeg] = int(m.group(1)) if m else 99
    return _FFMPEG_MAJOR[ffmpeg]


def vfr_args(ffmpeg: str = "ffmpeg") -> List[str]:
    """Variable-frame-rate output flag: -fps_mode (ffmpeg 5.1+) or the older -vsync."""
    return ["-fps_mode", "vfr"] if ffmpeg_major(ffmpeg) >= 5 else ["-vsync", "vfr"]


def parse_time(value: Any) -> float:
    """Accept seconds (int/float/str) or 'HH:MM:SS(.ms)' / 'MM:SS(.ms)'."""
    if isinstance(value, bool):
        raise ValueError(f"Invalid time: {value!r}")
    if isinstance(value, (int, float)):
        seconds = float(value)
    elif isinstance(value, str) and value.strip():
        parts = value.strip().split(":")
        if len(parts) > 3:
            raise ValueError(f"Invalid time: {value!r}")
        try:
            numbers = [float(p) for p in parts]
        except ValueError:
            raise ValueError(f"Invalid time: {value!r}") from None
        seconds = 0.0
        for n in numbers:
            seconds = seconds * 60 + n
    else:
        raise ValueError(f"Invalid time: {value!r}")
    if seconds < 0:
        raise ValueError(f"Negative time: {value!r}")
    return seconds


def format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def slugify(text: str, fallback: str = "video", max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].strip("-") or fallback


def read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    tmp.replace(path)


class Workspace:
    """Paths inside outputs/<video-name>/."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.reels = self.root / "reels"
        self.photos = self.root / "photos"
        self.samples = self.root / "samples"
        self.verify = self.samples / "verify"
        self.sheets = self.samples / "sheets"
        self.meta = self.root / "meta.json"
        self.source_info = self.root / "source_info.json"
        self.plan = self.root / "plan.json"
        self.render_report = self.root / "render_report.json"
        self.verify_report = self.root / "verify_report.json"
        self.analysis = self.root / "analysis"
        self.captions = self.root / "captions.md"

    def create(self) -> "Workspace":
        for d in (self.reels, self.photos, self.samples):
            d.mkdir(parents=True, exist_ok=True)
        return self


def reel_filename(reel: Dict[str, Any]) -> str:
    return f"reel_{reel['id']}_{slugify(str(reel.get('slug') or 'clip'))}.mp4"


def canvas_filename(reel: Dict[str, Any]) -> str:
    return reel_filename(reel)[:-4] + f"_{CANVAS_W}x{CANVAS_H}.mp4"


def photo_filename(photo: Dict[str, Any]) -> str:
    ext = photo.get("format", "jpg")
    return f"photo_{photo['id']}_{slugify(str(photo.get('slug') or 'still'))}.{ext}"


def emit(data: Any) -> None:
    """Print a JSON result for the calling agent."""
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def fail(message: str, code: int = 1) -> None:
    sys.stderr.write(f"error: {message}\n")
    sys.exit(code)


def chunks(items: Iterable[Any], size: int) -> List[List[Any]]:
    out: List[List[Any]] = []
    for item in items:
        if not out or len(out[-1]) >= size:
            out.append([])
        out[-1].append(item)
    return out


def optional_module(name: str) -> Optional[Any]:
    try:
        return __import__(name)
    except Exception:
        return None
