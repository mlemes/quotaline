import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


def test_marketplace_lists_this_plugin_by_its_manifest_name() -> None:
    plugin, market = load(".claude-plugin/plugin.json"), load(".claude-plugin/marketplace.json")
    assert "version" not in plugin  # updates follow the git commit SHA
    [entry] = market["plugins"]
    assert entry == {**entry, "name": plugin["name"], "source": "./"}


def test_hook_and_skills_call_the_installer_with_plugin_data() -> None:
    hook = load("hooks/hooks.json")["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "install.sh" in hook and "${CLAUDE_PLUGIN_DATA}" in hook and "--sync" in hook
    for name in ("install", "uninstall"):
        text = (ROOT / "skills" / name / "SKILL.md").read_text()
        assert re.search(r"^disable-model-invocation: true$", text, re.M), name
        assert '--dest "${CLAUDE_PLUGIN_DATA}"' in text, name
