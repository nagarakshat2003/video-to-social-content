import json
import math
import sys
import types
from pathlib import Path

import pytest
from conftest import ffmpeg

import analyze as analyze_mod
from analyze import analyze, candidates, import_subtitles


@pytest.fixture(scope="module")
def gap_clip(tmp_path_factory):
    """10 s: tone 0-3 s, silence 3-5 s, loud tone 5-10 s; hard visual cut at 5 s."""
    d = tmp_path_factory.mktemp("gap")
    out = d / "gap.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=5", "-f", "lavfi", "-i", "color=c=red:s=320x180:r=25:d=5",
           "-f", "lavfi", "-i", "sine=f=440:d=3,volume=0.3,apad=whole_dur=5",
           "-f", "lavfi", "-i", "sine=f=660:d=5,volume=0.9",
           "-filter_complex", "[0:v][2:a][1:v][3:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out))
    return out


@pytest.fixture
def gap_ws(tmp_path, gap_clip):
    from prepare import prepare
    return Path(prepare(str(gap_clip), "gap", tmp_path / "outputs")["workspace"])


def test_analyze_structure(gap_ws):
    result = analyze(gap_ws, transcribe_audio=False, min_len=3, max_len=8)
    a = gap_ws / "analysis"
    scenes = json.loads((a / "scenes.json").read_text())["cuts"]
    assert any(abs(t - 5.0) < 0.1 for t in scenes), scenes

    silences = json.loads((a / "silences.json").read_text())["silences"]
    assert any(abs(s["start"] - 3.0) < 0.3 and abs(s["end"] - 5.0) < 0.3 for s in silences), silences

    loud = json.loads((a / "loudness.json").read_text())["momentary_max_per_second"]
    assert len(loud) == 10 and loud[7] > loud[1] > loud[4]  # loud tone > quiet tone > silence

    sheets = json.loads((a / "sheets.json").read_text())
    tiles = [t for s in sheets["sheets"] for t in s["tiles"]]
    assert sheets["scale"] == 1.0 and len(sheets["sheets"]) == math.ceil(len(tiles) / 12)
    assert [t["t"] for t in tiles][:3] == [0.0, 1.0, 2.0]
    assert all(Path(s["file"]).is_file() for s in sheets["sheets"])

    assert result["transcript"]["engine"] is None and "--no-transcribe" in result["notes"][0]
    assert not (a / "transcript.json").exists()
    cands = json.loads((a / "candidates.json").read_text())
    assert cands["based_on"] == "audio/scene structure only" and cands["candidates"]
    for c in cands["candidates"]:
        assert 3 <= c["length"] <= 8


def test_analyze_is_cached(gap_ws, monkeypatch):
    analyze(gap_ws, transcribe_audio=False, min_len=3, max_len=8)
    calls = []
    monkeypatch.setattr(analyze_mod, "ffmpeg_pass", lambda *a, **k: calls.append(1))
    analyze(gap_ws, transcribe_audio=False, min_len=3, max_len=8)
    assert calls == []


def test_fake_faster_whisper(gap_ws, monkeypatch):
    calls = []

    class Word:
        def __init__(self, start, end, word):
            self.start, self.end, self.word, self.probability = start, end, word, 0.9

    class Segment:
        def __init__(self, start, end, text):
            self.start, self.end, self.text = start, end, text
            self.words = [Word(start, end, w) for w in text.split()]

    class WhisperModel:
        def __init__(self, name, **kw):
            calls.append(name)

        def transcribe(self, path, **kw):
            assert kw["word_timestamps"] is True
            return iter([Segment(0.2, 2.8, "Did you hear that?"), Segment(5.1, 9.5, "Wow, that is loud!")]), \
                types.SimpleNamespace(language="en")

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=WhisperModel))
    result = analyze(gap_ws, model="tiny", min_len=3, max_len=10)
    assert result["transcript"] == {"engine": "faster-whisper", "segments": 2,
                                    "file": str(gap_ws / "analysis" / "transcript.json")}
    data = json.loads((gap_ws / "analysis" / "transcript.json").read_text())
    assert data["language"] == "en" and data["segments"][0]["words"][0]["word"] == "Did"
    cands = json.loads((gap_ws / "analysis" / "candidates.json").read_text())
    assert cands["based_on"] == "transcript"
    assert cands["candidates"][0]["start"] in (0.2, 5.1)  # windows start on sentence boundaries

    analyze(gap_ws, model="tiny", min_len=3, max_len=10)
    assert calls == ["tiny"]  # cached the second time
    analyze(gap_ws, model="base", min_len=3, max_len=10)
    assert calls == ["tiny", "base"]  # a different model invalidates the cache


SRT = """1
00:00:01,000 --> 00:00:03,500
Hello <i>there</i>!

2
00:00:04,000 --> 00:00:06,000
How are you &amp; the team?
"""

VTT = """WEBVTT

00:00:00.000 --> 00:00:02.000
we built

00:00:02.000 --> 00:00:04.000
we built the whole thing

00:00:04.000 --> 00:00:05.000
we built the whole thing
"""


def test_import_subtitles(tmp_path):
    srt = tmp_path / "a.srt"
    srt.write_text(SRT)
    segs = import_subtitles(srt)["segments"]
    assert [(s["start"], s["end"], s["text"]) for s in segs] == [
        (1.0, 3.5, "Hello there!"), (4.0, 6.0, "How are you & the team?")]

    vtt = tmp_path / "a.vtt"
    vtt.write_text(VTT)
    segs = import_subtitles(vtt)["segments"]
    assert [(s["start"], s["end"], s["text"]) for s in segs] == [(0.0, 2.0, "we built"), (2.0, 5.0, "the whole thing")]


def test_analyze_with_subtitles(gap_ws, tmp_path):
    srt = tmp_path / "s.srt"
    srt.write_text(SRT)
    result = analyze(gap_ws, subtitles=srt, min_len=3, max_len=8)
    assert result["transcript"]["engine"] == "subtitles" and result["transcript"]["segments"] == 2


def test_candidates_scoring_and_overlap():
    transcript = {"segments": [
        {"start": 0, "end": 10, "text": "and then we kept going with the plan as usual"},
        {"start": 10, "end": 20, "text": "Why did we lose two million dollars in two days?"},
        {"start": 20, "end": 30, "text": "Because nobody checked the numbers haha!"},
        {"start": 30, "end": 40, "text": "so anyway that is the story of the launch week"},
    ]}
    loud = [-30.0] * 40
    for s in range(10, 30):
        loud[s] = -18.0
    out = candidates(40, transcript, loud, scenes=[], silences=[], top=3, min_len=15, max_len=25)
    best = out[0]
    assert (best["start"], best["end"]) == (10, 30)
    assert "punchy opening line" in best["reasons"] and "laughter/humor cue" in best["reasons"]
    assert any("louder" in r for r in best["reasons"])
    for a in out:
        for b in out:
            if a is not b:
                inter = max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
                assert inter / min(a["length"], b["length"]) < 0.3
    weak = [c for c in out if c["start"] == 0]
    assert not weak or any("starts with 'and'" in r for r in weak[0]["reasons"])


def test_candidates_short_video_and_no_structure():
    out = candidates(9.0, {"segments": []}, [], [], [], top=5, min_len=15, max_len=60)
    assert out and all(c["end"] <= 9.0 for c in out)


def test_old_ffmpeg_vsync_fallback(gap_ws, monkeypatch):
    import common

    monkeypatch.setitem(common._FFMPEG_MAJOR, "ffmpeg", 4)
    monkeypatch.setitem(common._FFMPEG_MAJOR, common.require("ffmpeg"), 4)
    assert common.vfr_args(common.require("ffmpeg")) == ["-vsync", "vfr"]
    result = analyze(gap_ws, transcribe_audio=False, min_len=3, max_len=8, force=True)
    assert result["contact_sheets"]
