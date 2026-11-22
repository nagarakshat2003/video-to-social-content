"""track_subject.py: decision logic with synthetic detections, and the plan update with a fake detector."""

import json

import pytest
from conftest import write_plan

import track_subject as ts


def test_pick_primary_prefers_largest_then_continuity():
    small_left, big_right = (10, 10, 50, 50), (400, 10, 60, 60)
    assert ts.pick_primary([small_left, big_right], None) == big_right
    assert ts.pick_primary([(10, 10, 55, 55), big_right], prev_center=40) == (10, 10, 55, 55)
    assert ts.pick_primary([], None) is None


def test_decide_static():
    samples = [(t, 500 + (t % 2) * 10) for t in range(10)]
    d = ts.decide(samples, crop_size=200, axis="x", allow_track=True)
    assert d["decision"] == "static" and 495 <= d["subject_x"] <= 510


def test_decide_pan_is_simplified():
    samples = [(float(t), 100 + t * 50) for t in range(12)]  # steady drift 100 -> 650
    d = ts.decide(samples, crop_size=200, axis="x", allow_track=True)
    assert d["decision"] == "pan"
    track = d["subject_track"]
    assert track[0] == {"t": 0.0, "x": 100} and track[-1] == {"t": 11.0, "x": 650}
    assert len(track) == 2  # a straight line needs only its endpoints


def test_decide_split_for_two_speakers():
    samples = [(float(t), 150 if t % 4 < 2 else 900) for t in range(12)]
    d = ts.decide(samples, crop_size=300, axis="x", allow_track=True)
    assert d["decision"] == "split" and d["jumps"] >= 2


def test_decide_photo_cannot_pan_and_none():
    moving = [(0.0, 100), (1.0, 300), (2.0, 500)]
    assert ts.decide(moving, 100, "x", allow_track=False)["decision"] == "split"
    assert ts.decide([(0.0, None), (1.0, None), (2.0, None), (3.0, 300)], 100, "x", True)["decision"] == "none"  # 25% < 30%


def test_sample_times():
    times = ts.sample_times(10.0, 40.0)
    assert times[0] == 10.0 and times[-1] <= 39.95 and len(times) <= ts.MAX_SAMPLES + 1


def test_track_writes_plan_with_fake_detector(workspace, monkeypatch):
    plan = {"reels": [{"id": "01", "start": 0, "end": 6},
                      {"id": "02", "start": 1, "end": 7, "subject_x": 50}],
            "photos": [{"id": "01", "time": 2}]}
    plan_path = write_plan(workspace, plan)

    # Fake detector: one face whose x drifts with the frame index (source is 640 wide; analysis is 640 wide too).
    counter = {"n": 0}

    def fake_detect(detectors, image, scale):
        counter["n"] += 1
        return [(100 + 25 * counter["n"], 50, 40, 40)]

    monkeypatch.setattr(ts, "detect_faces", fake_detect)
    report = ts.track(plan_path, write=True, detectors=object())
    by_id = {(i["kind"], i["id"]): i for i in report["items"]}
    assert by_id[("reel", "01")]["decision"] == "pan"
    assert by_id[("reel", "02")]["decision"] == "kept"
    assert by_id[("photo", "01")]["decision"] == "static"

    saved = json.loads(plan_path.read_text())
    assert "subject_track" in saved["reels"][0] and saved["reels"][1]["subject_x"] == 50
    assert isinstance(saved["photos"][0]["subject_x"], int)
    assert (workspace / "plan.json.bak").is_file()

    import plan as plan_mod
    _, _, _, errors, _ = plan_mod.load(plan_path)
    assert errors == []  # the written plan is valid


def test_missing_opencv_message(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_cv2(name, *a, **k):
        if name == "cv2":
            raise ImportError
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_cv2)
    with pytest.raises(ts.ToolError, match="opencv-python-headless"):
        ts.load_detectors()
