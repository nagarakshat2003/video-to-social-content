#!/usr/bin/env python3
"""
captions.py - Scaffold and check outputs/<name>/captions.md.

  scaffold  Write captions.md with every factual field pre-filled from the
            plan (file names, links, timestamps, resolutions, transcript
            excerpts, source attribution, copyright reminder). The agent only
            replaces the TODO markers with the creative text.
  check     Fail while any TODO marker remains or a planned output is not
            mentioned, so the agent cannot finish with a half-written file.

Usage:
  captions.py scaffold outputs/<name>/plan.json [--force]
  captions.py check outputs/<name>/plan.json
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import plan as plan_mod
from common import emit, fail, format_time, read_json

TODO = "TODO"
CC_RE = re.compile(r"creative\s*commons|\bcc[\s-]?by\b", re.I)


def load_transcript(ws) -> Optional[List[Dict[str, Any]]]:
    path = ws.analysis / "transcript.json"
    if not path.is_file():
        return None
    data = read_json(path)
    return data.get("segments") if isinstance(data, dict) else None


def excerpt(segments: Optional[List[Dict[str, Any]]], start: float, end: float, limit: int = 700) -> Optional[str]:
    if not segments:
        return None
    text = " ".join(s["text"].strip() for s in segments if s["end"] > start and s["start"] < end).strip()
    if not text:
        return None
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


def scaffold_text(ws, meta: Dict[str, Any], resolved: Dict[str, Any]) -> str:
    info = read_json(ws.source_info) if ws.source_info.is_file() else None
    segments = load_transcript(ws)
    title = (info or {}).get("title") or meta.get("name") or Path(meta["source"]).stem
    lines: List[str] = [f"# Social Content: {title}", ""]

    if info:
        who = info.get("uploader") or "unknown uploader"
        lines.append(f"**Source:** \"{info.get('title')}\" by {who} — {info.get('url')}")
        if CC_RE.search(info.get("license") or ""):
            lines.append(f"**License:** {info['license']} — credit the creator as the license requires.")
        else:
            lines.append("**Copyright:** This footage belongs to a third party. Posting it publicly may lead to "
                         "copyright claims or DMCA takedowns unless you own it or have a license.")
    else:
        lines.append(f"**Source:** `{Path(meta['source']).name}`")
        lines.append(f"**Rights:** {TODO}: say whether this is the user's own footage. If it comes from a film, "
                     "TV broadcast or another creator, replace this line with a copyright reminder.")
    lines += ["", "## Deliverables", "",
              "| Output File | Type | Timestamp Range | Genre / Theme | Resolution | Key Hook / Headline |",
              "| :--- | :--- | :--- | :--- | :--- | :--- |"]
    for r in resolved["reels"]:
        span = f"{format_time(r['start_s'])} – {format_time(r['end_s'])}"
        lines.append(f"| [{r['file']}](reels/{r['file']}) | {r['ratio']} Reel | {span} | "
                     f"{r.get('genre') or TODO} | {r['crop']['resolution']} | {r.get('hook') or TODO} |")
        if r.get("canvas_file"):
            lines.append(f"| [{r['canvas_file']}](reels/{r['canvas_file']}) | 9:16 Reel (blurred canvas) | {span} | "
                         f"{r.get('genre') or TODO} | 1080x1920 | (same as above) |")
    for p in resolved["photos"]:
        lines.append(f"| [{p['file']}](photos/{p['file']}) | {p['ratio']} Still | {format_time(p['time_s'])} | "
                     f"Carousel {p.get('carousel', 1)} | {p['crop']['resolution']} | {p.get('theme') or '—'} |")

    if resolved["reels"]:
        lines += ["", "## Reels"]
    for r in resolved["reels"]:
        lines += ["", f"### Reel {r['id']} — {r.get('genre') or 'Untitled'}",
                  f"`{r['file']}` · {format_time(r['start_s'])} – {format_time(r['end_s'])} "
                  f"({r['duration_s']:.1f}s) · {r['crop']['resolution']}", ""]
        quote = excerpt(segments, r["start_s"], r["end_s"])
        if quote:
            lines += ["Transcript (machine-generated; quote only words that appear here):", "", f"> {quote}", ""]
        lines += [f"- **Hook:** {r.get('hook') or TODO}",
                  f"- **Caption:** {TODO}: 1–3 sentences of context in the video's tone.",
                  f"- **CTA:** {TODO}",
                  f"- **Hashtags:** {TODO}: 3–5 relevant tags.",
                  f"- **On-screen text:** {TODO}",
                  f"- **Content flags:** {TODO}: `none`, or e.g. `[Mature / Violence]` with platform risk notes."]

    carousels: Dict[Any, List[Dict[str, Any]]] = {}
    for p in resolved["photos"]:
        carousels.setdefault(p.get("carousel", 1), []).append(p)
    if carousels:
        lines += ["", "## Photo Carousels"]
    for key, photos in carousels.items():
        lines += ["", f"### Carousel {key}", "", "Slide order:"]
        for n, p in enumerate(photos, start=1):
            lines.append(f"{n}. [{p['file']}](photos/{p['file']}) — {format_time(p['time_s'])}")
        lines += ["", f"- **Caption:** {TODO}: 80–200 words telling the story of the moment.",
                  f"- **Question / reflection:** {TODO}",
                  f"- **Hashtags:** {TODO}"]
    lines.append("")
    return "\n".join(lines)


def scaffold(plan_path: Path, force: bool = False) -> Dict[str, Any]:
    ws, meta, resolved, errors, _ = plan_mod.load(plan_path)
    if errors:
        return {"ok": False, "errors": errors}
    if ws.captions.is_file() and not force:
        return {"ok": False, "errors": [f"{ws.captions} already exists; edit it, or pass --force to overwrite"]}
    text = scaffold_text(ws, meta, resolved)
    ws.captions.write_text(text, encoding="utf-8")
    return {"ok": True, "errors": [], "file": str(ws.captions), "todo_markers": text.count(TODO)}


def check(plan_path: Path) -> Dict[str, Any]:
    ws, _, resolved, errors, _ = plan_mod.load(plan_path)
    if errors:
        return {"ok": False, "errors": errors, "problems": []}
    if not ws.captions.is_file():
        return {"ok": False, "errors": [], "problems": [f"{ws.captions} does not exist; run 'captions.py scaffold' first"]}
    text = ws.captions.read_text(encoding="utf-8")
    problems = []
    todo_lines = [i + 1 for i, line in enumerate(text.splitlines()) if TODO in line]
    if todo_lines:
        problems.append(f"{len(todo_lines)} TODO marker(s) left on lines {todo_lines[:20]}")
    files = [r["file"] for r in resolved["reels"]] + [p["file"] for p in resolved["photos"]]
    missing = [f for f in files if f not in text]
    if missing:
        problems.append(f"outputs not mentioned: {missing}")
    for r in resolved["reels"]:
        section = re.search(rf"### Reel {re.escape(r['id'])}\b(.*?)(?=\n### |\n## |\Z)", text, re.S)
        if section:
            tags = re.findall(r"(?<!\w)#\w+", section.group(1))
            if not 3 <= len(tags) <= 5:
                problems.append(f"reel {r['id']}: {len(tags)} hashtags, expected 3–5")
    return {"ok": not problems, "errors": [], "problems": problems, "file": str(ws.captions)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["scaffold", "check"])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--force", action="store_true", help="scaffold: overwrite an existing captions.md")
    args = parser.parse_args()
    try:
        result = scaffold(args.plan, args.force) if args.action == "scaffold" else check(args.plan)
    except FileNotFoundError as exc:
        fail(str(exc))
    emit(result)
    if result.get("errors"):
        raise SystemExit(2)
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
