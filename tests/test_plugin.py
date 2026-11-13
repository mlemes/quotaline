import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


def test_marketplace_lists_this_plugin_by_its_manifest_name() -> None:
    plugin, market = load(".claude-plugin/plugin.json"), load(".claude-plugin/marketplace.json")
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert f'version = "{plugin["version"]}"' in pyproject  # users update only on a bump
    [entry] = [item for item in market["plugins"] if item["name"] == plugin["name"]]
    assert entry == {**entry, "name": plugin["name"], "source": "./"}


def test_plugin_declares_no_command_hooks() -> None:
    assert not (ROOT / "hooks" / "hooks.json").exists()
    assert "hooks" not in load(".claude-plugin/plugin.json")


def test_skills_call_the_installer_with_plugin_data() -> None:
    for name in ("install", "uninstall"):
        text = (ROOT / "skills" / name / "SKILL.md").read_text()
        assert re.search(r"^disable-model-invocation: true$", text, re.M), name
        assert '--dest "${CLAUDE_PLUGIN_DATA}"' in text, name
