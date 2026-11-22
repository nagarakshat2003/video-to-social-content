"""Shared fixtures: small synthetic clips generated with ffmpeg's lavfi sources."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "video-to-social-content" / "scripts"
sys.path.insert(0, str(SCRIPTS))

FAST = "ultrafast"  # x264 preset for tests; the plugin default stays "slow"

if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
    pytest.skip("ffmpeg/ffprobe not installed", allow_module_level=True)


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", *args], check=True)


@pytest.fixture(scope="session")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips")
    out = {}

    # 640x360, 8 s, tone audio, hard scene cut at 4 s, quiet first half / loud second half.
    out["landscape"] = d / "landscape.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=4",
           "-f", "lavfi", "-i", "smptebars=s=640x360:r=25:d=4",
           "-f", "lavfi", "-i", "sine=f=440:d=4,volume=0.05",
           "-f", "lavfi", "-i", "sine=f=880:d=4,volume=0.9",
           "-filter_complex", "[0:v][2:a][1:v][3:a]concat=n=2:v=1:a=1[v][a]",
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", FAST, "-pix_fmt", "yuv420p",
           "-c:a", "aac", str(out["landscape"]))

    # Phone-style: coded 640x360 with 90 degree rotation metadata -> displays as 360x640.
    out["rotated"] = d / "rotated.mp4"
    from common import ffmpeg_major
    if ffmpeg_major() >= 6:
        ffmpeg("-display_rotation", "90", "-i", str(out["landscape"]), "-c", "copy", str(out["rotated"]))
    else:  # ffmpeg < 6 writes rotation as a stream tag
        ffmpeg("-i", str(out["landscape"]), "-c", "copy", "-metadata:s:v:0", "rotate=90", str(out["rotated"]))

    # 4:5 portrait without audio.
    out["portrait_silent"] = d / "portrait_silent.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=360x450:r=25:d=5", "-c:v", "libx264", "-preset", FAST,
           "-pix_fmt", "yuv420p", str(out["portrait_silent"]))
    return out


@pytest.fixture
def workspace(tmp_path, clips):
    """A prepared workspace for the landscape clip."""
    from prepare import prepare

    result = prepare(str(clips["landscape"]), "landscape", tmp_path / "outputs")
    return Path(result["workspace"])


def write_plan(ws: Path, plan: dict) -> Path:
    path = ws / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path
