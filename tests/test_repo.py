"""Repository consistency: rules in sync, manifests valid, docs only reference files that exist."""

import json
import re
import subprocess
import sys

from conftest import ROOT, SCRIPTS


def test_rules_copies_in_sync():
    proc = subprocess.run([sys.executable, str(ROOT / "tools" / "sync_rules.py"), "--check"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_manifests_are_valid_json():
    for path in ["plugin.json", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
                 ".codex-plugin/plugin.json", ".agents/plugins/marketplace.json"]:
        data = json.loads((ROOT / path).read_text())
        assert data.get("name"), path


def test_versions_match():
    versions = {json.loads((ROOT / p).read_text())["version"]
                for p in ["plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"]}
    assert len(versions) == 1, versions


def test_docs_reference_existing_scripts_and_references():
    skill_dir = SCRIPTS.parent
    docs = [skill_dir / "SKILL.md", ROOT / "AGENTS.md", ROOT / "CLAUDE.md", ROOT / "README.md",
            ROOT / "agents" / "video-editor.md", ROOT / "commands" / "video-to-social-content.md"]
    for doc in docs:
        text = doc.read_text()
        for script in set(re.findall(r"\b([a-z_]+\.py)\b", text)):
            assert (SCRIPTS / script).is_file() or (ROOT / "tools" / script).is_file(), f"{doc.name}: {script}"
        for ref in set(re.findall(r"references/([a-z-]+\.md)", text)):
            assert (skill_dir / "references" / ref).is_file(), f"{doc.name}: references/{ref}"


def test_scripts_have_help():
    for script in sorted(SCRIPTS.glob("*.py")):
        if script.name == "common.py":
            continue
        proc = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, cwd=SCRIPTS)
        assert proc.returncode == 0 and "usage" in proc.stdout.lower(), script.name
