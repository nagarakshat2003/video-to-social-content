import random
import subprocess
import sys

import pytest
from conftest import SCRIPTS

from common import format_time, parse_time, slugify
from crop_math import RATIOS, calculate_crop


@pytest.mark.parametrize("value,expected", [
    (12, 12.0), (1.5, 1.5), ("7.25", 7.25), ("01:30", 90.0), ("00:01:14.500", 74.5), ("1:00:00", 3600.0),
])
def test_parse_time(value, expected):
    assert parse_time(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", ["", "abc", "1:2:3:4", -1, True, None, "-5"])
def test_parse_time_rejects(value):
    with pytest.raises(ValueError):
        parse_time(value)


def test_format_time_round_trip():
    assert format_time(3723.456) == "01:02:03.456"
    assert parse_time(format_time(74.5)) == pytest.approx(74.5)


def test_slugify():
    assert slugify("Startup Lessons: The $2M Mistake!") == "startup-lessons-the-2m-mistake"
    assert slugify("Café — naïve") == "cafe-naive"
    assert slugify("!!!") == "video"


@pytest.mark.parametrize("w,h,ratio,kw,expected", [
    (1920, 1080, "9:16", {"subject_x": 1700}, "crop=606:1080:1314:0"),
    (1920, 1080, "3:4", {}, "crop=810:1080:555:0"),
    (1080, 1350, "9:16", {}, "crop=758:1350:161:0"),          # 4:5 is wider than 9:16 -> crop width
    (1080, 1920, "3:4", {"subject_y": 300}, "crop=1080:1440:0:0"),
    (1080, 1920, "9:16", {}, "crop=1080:1920:0:0"),
])
def test_crop_examples(w, h, ratio, kw, expected):
    assert calculate_crop(w, h, ratio, **kw)["ffmpeg_filter"] == expected


def test_crop_always_fits_and_is_even():
    rng = random.Random(7)
    for _ in range(20000):
        w, h = rng.randint(2, 4000), rng.randint(2, 4000)
        ratio = rng.choice(list(RATIOS))
        sx = rng.choice([None, rng.randint(-500, w + 500)])
        sy = rng.choice([None, rng.randint(-500, h + 500)])
        try:
            c = calculate_crop(w, h, ratio, sx, sy)
        except ValueError:
            continue  # sources too small to crop
        assert c["crop_w"] % 2 == 0 and c["crop_h"] % 2 == 0
        assert 2 <= c["crop_w"] <= w and 2 <= c["crop_h"] <= h
        assert 0 <= c["offset_x"] <= w - c["crop_w"]
        assert 0 <= c["offset_y"] <= h - c["crop_h"]


def test_crop_rejects_tiny_source():
    with pytest.raises(ValueError):
        calculate_crop(800, 2, "9:16")


def test_crop_math_cli():
    out = subprocess.run([sys.executable, str(SCRIPTS / "crop_math.py"), "-W", "1920", "-H", "1080", "-x", "1700"],
                         capture_output=True, text=True, check=True).stdout
    assert "Crop Filter: crop=606:1080:1314:0" in out


def test_probe(clips):
    from probe import probe

    meta = probe(str(clips["landscape"]))
    assert (meta["width"], meta["height"], meta["rotation"]) == (640, 360, 0)
    assert meta["duration"] == pytest.approx(8.0, abs=0.1)
    assert meta["fps"] == 25 and meta["has_audio"]

    rotated = probe(str(clips["rotated"]))
    assert (rotated["coded_width"], rotated["coded_height"]) == (640, 360)
    assert (rotated["width"], rotated["height"]) == (360, 640)
    assert abs(rotated["rotation"]) == 90

    silent = probe(str(clips["portrait_silent"]))
    assert not silent["has_audio"] and silent["audio_codec"] is None


def test_prepare_local_file_is_not_copied(tmp_path, clips):
    from prepare import prepare

    result = prepare(str(clips["landscape"]), None, tmp_path / "outputs")
    ws = tmp_path / "outputs" / "landscape"
    assert result["workspace"] == str(ws)
    assert result["meta"]["source"] == str(clips["landscape"])
    assert (ws / "meta.json").is_file()
    assert all((ws / d).is_dir() for d in ("reels", "photos", "samples"))
    assert not list(ws.glob("source.*"))
    assert result["reel_resolution"] == "202x360" and result["reel_below_1080x1920"]
