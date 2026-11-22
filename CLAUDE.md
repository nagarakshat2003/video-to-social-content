# CLAUDE.md - Video to Social Content Project Instructions

This repository houses the **Video to Social Content** plugin for turning video footage and URLs into platform-ready 9:16 vertical reels, 3:4 photo carousels, and engaging captions.

## Behavioural rules

The rules for handling video (non-destructive outputs, subject-aware cropping, encoding, verification, factual integrity, ethics) live in one place and are imported here:

@AGENTS.md

## Repository layout

- `skills/video-to-social-content/SKILL.md` — the workflow the agent follows.
- `skills/video-to-social-content/scripts/` — the pipeline (standard library only, Python 3.8+): `prepare.py`, `analyze.py`, `track_subject.py`, `plan.py`, `render.py`, `verify.py`, `captions.py`, plus `common.py`, `probe.py`, `crop_math.py`.
- `skills/video-to-social-content/references/` — detail loaded on demand (plan format, caption guidelines, manual fallback commands).
- `tests/` — pytest suite using generated clips; `evals/` — end-to-end plugin eval cases.

## Development commands

```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
python3 tools/sync_rules.py          # after editing AGENTS.md (CI runs --check)
claude plugin validate .
```

## Conventions

- Put mechanical work in scripts, not in SKILL.md prose; SKILL.md should only tell the agent which script to run and what to judge.
- Scripts print JSON, exit non-zero on failure, and must not modify the source video.
- Every script change needs a test in `tests/`.
- Edit `AGENTS.md` only, then run `tools/sync_rules.py`; never edit `rules/AGENTS.md` by hand.
