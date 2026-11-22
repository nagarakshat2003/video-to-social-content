#!/usr/bin/env python3
"""
sync_rules.py - Keep the rule copies identical to the single source, AGENTS.md.

AGENTS.md (repo root) is the source of truth. rules/AGENTS.md is the copy
Antigravity loads as an always-on rule. CLAUDE.md imports AGENTS.md with
"@AGENTS.md" instead of duplicating it.

Usage:
  python3 tools/sync_rules.py          # copy AGENTS.md over the copies
  python3 tools/sync_rules.py --check  # exit 1 if any copy has drifted (CI)
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "AGENTS.md"
COPIES = [ROOT / "rules" / "AGENTS.md"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = SOURCE.read_text(encoding="utf-8")
    drifted = [c for c in COPIES if not c.is_file() or c.read_text(encoding="utf-8") != text]
    if args.check:
        for c in drifted:
            print(f"{c.relative_to(ROOT)} differs from AGENTS.md; run: python3 tools/sync_rules.py", file=sys.stderr)
        return 1 if drifted else 0
    for c in drifted:
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(text, encoding="utf-8")
        print(f"updated {c.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
