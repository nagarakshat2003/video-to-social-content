import json
import subprocess

import pytest
from conftest import FAST, write_plan

import plan as plan_mod
from captions import check as captions_check
from captions import scaffold
from render import render, track_expression
from verify import verify

GOOD_PLAN = {
    "reels": [
        {"id": "01", "slug": "Intro Beat", "start": 0, "end": "00:00:05.0", "subject_x": 500, "genre": "Intro",
         "hook": "Watch the bars"},
        {"id": "02", "slug": "pan", "start": 1, "end": 7, "ratio": "3:4",
         "subject_track": [{"t": 1, "x": 100}, {"t": 7, "x": 600}], "canvas": True},
    ],
    "photos": [
        {"id": "01", "slug": "bars", "time": 6, "subject_x": 320, "carousel": 1},
        {"id": "02", "slug": "square", "time": "00:00:02", "ratio": "1:1", "format": "png", "carousel": 1},
    ],
}


def resolve(plan, meta=None):
    meta = meta or {"width": 640, "height": 360, "duration": 8.0}
    return plan_mod.resolve(plan, meta)


def test_plan_resolves_files_and_crops():
    resolved, errors, warnings = resolve(GOOD_PLAN)
    assert errors == []
    r1, r2 = resolved["reels"]
    assert r1["file"] == "reel_01_intro-beat.mp4" and r1["crop"]["ffmpeg_filter"] == "crop=202:360:399:0"
    assert r2["track_offsets"] == [(0.0, 0), (6.0, 370)]  # 3:4 crop is 270 wide; max x = 640 - 270
    assert r2["canvas_file"] == "reel_02_pan_1080x1920.mp4"
    assert [p["file"] for p in resolved["photos"]] == ["photo_01_bars.jpg", "photo_02_square.png"]
    assert any("recommended" in w for w in warnings)  # 5-6 s reels are under 15 s


@pytest.mark.parametrize("plan,fragment", [
    ({}, "no reels and no photos"),
    ({"reels": [{"id": "a b", "start": 0, "end": 5}]}, "'id' is required"),
    ({"reels": [{"id": "1", "start": 5, "end": 2}]}, "must be after start"),
    ({"reels": [{"id": "1", "start": 0, "end": 2}]}, "outside the 3-90s limit"),
    ({"reels": [{"id": "1", "start": 0, "end": 7, "ratio": "16:9"}]}, "ratio must be one of"),
    ({"reels": [{"id": "1", "start": 0, "end": 9}]}, "past the video's end"),
    ({"reels": [{"id": "1", "start": "x", "end": 5}]}, "Invalid time"),
    ({"reels": [{"id": "1", "start": 0, "end": 5, "subject_x": "left"}]}, "subject_x must be a number"),
    ({"reels": [{"id": "1", "start": 0, "end": 5, "subject_track": [{"t": 0, "x": 1}]}]}, "at least 2"),
    ({"reels": [{"id": "1", "start": 0, "end": 5}, {"id": "1", "start": 0, "end": 5}]}, "duplicate output"),
    ({"photos": [{"id": "1", "time": 8}]}, "past the video's end"),
    ({"photos": [{"id": "1", "time": 1, "format": "gif"}]}, "format must be"),
])
def test_plan_errors(plan, fragment):
    _, errors, _ = resolve(plan)
    assert any(fragment in e for e in errors), errors


def test_track_expression_is_piecewise_linear():
    assert track_expression([(0.0, 0), (6.0, 360)]) == "if(lt(t,6),0+(360)*(t-0)/6,360)"
    assert track_expression([(1.0, 10), (2.0, 20)]).startswith("if(lt(t,1),10,")


def test_render_and_verify_end_to_end(workspace):
    plan_path = write_plan(workspace, GOOD_PLAN)
    report = render(plan_path, preset=FAST, jobs=2)
    assert report["ok"], report
    assert {i["status"] for i in report["items"]} == {"rendered"}
    assert any("below 1080x1920" in w for w in report["warnings"])

    result = verify(plan_path)
    assert result["ok"], json.dumps(result, indent=1)
    assert result["passed"] == 4
    reel1 = next(i for i in result["items"] if i["id"] == "01" and i["kind"] == "reel")
    assert reel1["resolution"] == "202x360" and reel1["has_audio"]
    assert reel1["duration"] == pytest.approx(5.0, abs=0.15)
    assert len(result["review_images"]) == 3  # two reel sheets + one photo sheet
    assert (workspace / "verify_report.json").is_file()

    # Re-running render skips existing outputs.
    again = render(plan_path, preset=FAST)
    assert all(i["status"].startswith("skipped") for i in again["items"])


def test_pan_actually_moves(workspace):
    plan_path = write_plan(workspace, {"reels": [GOOD_PLAN["reels"][1]]})
    assert render(plan_path, preset=FAST)["ok"]
    reel = workspace / "reels" / "reel_02_pan.mp4"

    def frame_bytes(seek):
        return subprocess.run(["ffmpeg", "-v", "error", *seek, "-i", str(reel), "-frames:v", "1",
                               "-vf", "scale=16:16,format=gray", "-f", "rawvideo", "-"],
                              capture_output=True, check=True).stdout

    assert frame_bytes([]) != frame_bytes(["-ss", "2.5"])


def test_verify_catches_bad_outputs(workspace):
    plan_path = write_plan(workspace, {"reels": [GOOD_PLAN["reels"][0]], "photos": [GOOD_PLAN["photos"][0]]})
    assert render(plan_path, preset=FAST)["ok"]
    reel = workspace / "reels" / "reel_01_intro-beat.mp4"
    bad = workspace / "bad.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(reel), "-vf", "scale=204:360", "-an",
                    "-c:v", "libx264", "-preset", FAST, str(bad)], check=True)
    bad.replace(reel)
    (workspace / "photos" / "photo_01_bars.jpg").unlink()
    (workspace / "photos" / "leftover.jpg").write_bytes(b"x")

    result = verify(plan_path)
    assert not result["ok"]
    failures = {i["id"] + i["kind"]: i["failures"] for i in result["items"]}
    reel_failures = " ".join(failures["01reel"])
    assert "size 204x360" in reel_failures and "no audio" in reel_failures and "faststart" in reel_failures
    assert failures["01photo"] == ["missing (run render.py)"]
    assert any("leftover.jpg" in w for w in result["warnings"])


def test_silent_portrait_source(tmp_path, clips):
    from prepare import prepare

    ws = __import__("pathlib").Path(prepare(str(clips["portrait_silent"]), "p", tmp_path / "o")["workspace"])
    plan_path = write_plan(ws, {"reels": [{"id": "01", "start": 0, "end": 4, "subject_y": 400}]})
    assert render(plan_path, preset=FAST)["ok"]
    result = verify(plan_path)
    assert result["ok"], result
    assert result["items"][0]["resolution"] == "252x450"
    assert not result["items"][0]["has_audio"]


def test_rotated_source_uses_display_size(tmp_path, clips):
    from prepare import prepare

    ws = __import__("pathlib").Path(prepare(str(clips["rotated"]), "r", tmp_path / "o")["workspace"])
    plan_path = write_plan(ws, {"photos": [{"id": "01", "time": 1, "ratio": "3:4"}]})
    assert render(plan_path, preset=FAST)["ok"]
    assert verify(plan_path)["items"][0]["resolution"] == "360x480"


def test_invalid_plan_is_not_rendered(workspace):
    plan_path = write_plan(workspace, {"reels": [{"id": "01", "start": 0, "end": 1}]})
    report = render(plan_path, preset=FAST)
    assert report["errors"] and not list((workspace / "reels").iterdir())


def test_dry_run_writes_nothing(workspace):
    plan_path = write_plan(workspace, GOOD_PLAN)
    report = render(plan_path, preset=FAST, dry_run=True)
    assert {i["status"] for i in report["items"]} == {"dry-run"}
    assert "-af afade=t=in:st=0:d=0.3" in report["items"][0]["commands"][0]
    assert not list((workspace / "reels").iterdir())


def test_captions_scaffold_and_check(workspace):
    plan_path = write_plan(workspace, GOOD_PLAN)
    (workspace / "analysis").mkdir()
    (workspace / "analysis" / "transcript.json").write_text(json.dumps(
        {"segments": [{"start": 0.5, "end": 3.0, "text": "Look at these colour bars."}]}))
    assert scaffold(plan_path)["ok"]
    text = (workspace / "captions.md").read_text()
    assert "> Look at these colour bars." in text
    assert "**Rights:** TODO" in text  # local file: the agent must state the rights
    assert "[reel_01_intro-beat.mp4](reels/reel_01_intro-beat.mp4)" in text
    assert not scaffold(plan_path)["ok"]  # refuses to overwrite

    first = captions_check(plan_path)
    assert not first["ok"] and "TODO" in first["problems"][0]

    filled = text.replace("TODO: 3–5 relevant tags.", "#bars #test #video")
    filled = "\n".join(line.split("TODO")[0] + "done" if "TODO" in line else line for line in filled.splitlines())
    (workspace / "captions.md").write_text(filled)
    assert captions_check(plan_path) == {"ok": True, "errors": [], "problems": [], "file": str(workspace / "captions.md")}


def test_captions_copyright_for_url_sources(workspace):
    plan_path = write_plan(workspace, GOOD_PLAN)
    (workspace / "source_info.json").write_text(json.dumps(
        {"url": "https://example.com/v", "title": "Clip", "uploader": "Someone", "license": None}))
    scaffold(plan_path)
    text = (workspace / "captions.md").read_text()
    assert '"Clip" by Someone' in text and "DMCA" in text and "Rights:" not in text
