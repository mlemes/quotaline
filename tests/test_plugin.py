import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


def test_plugin_version_matches_package_version() -> None:
    plugin = load(".claude-plugin/plugin.json")
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert f'version = "{plugin["version"]}"' in pyproject  # users update only on a bump


def test_plugin_declares_no_command_hooks() -> None:
    assert not (ROOT / "hooks" / "hooks.json").exists()
    assert "hooks" not in load(".claude-plugin/plugin.json")


def test_skills_call_the_installer_with_plugin_data() -> None:
    for name in ("install", "uninstall"):
        text = (ROOT / "skills" / name / "SKILL.md").read_text()
        assert re.search(r"^disable-model-invocation: true$", text, re.M), name
        assert '--dest "${CLAUDE_PLUGIN_DATA}"' in text, name
