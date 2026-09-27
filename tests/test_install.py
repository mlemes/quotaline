import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "install.sh"


def run(settings: Path, *args: str) -> str:
    env = {**os.environ, "CLAUDE_SETTINGS": str(settings)}
    return subprocess.run(
        ["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, check=True
    ).stdout


def test_install_is_idempotent_and_keeps_other_keys(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"model": "opus"}))
    run(settings)
    run(settings)
    s = json.loads(settings.read_text())
    assert s["model"] == "opus"
    assert s["statusLine"]["command"].endswith("python3 -m usage_statusline")
    backup = json.loads((tmp_path / "settings.json.bak-usage-statusline").read_text())
    assert backup == {"model": "opus"}


def test_install_creates_missing_settings(tmp_path: Path) -> None:
    settings = tmp_path / "new" / "settings.json"
    run(settings)
    assert "statusLine" in json.loads(settings.read_text())


def test_uninstall_removes_only_our_status_line(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"statusLine": {"type": "command", "command": "other"}}))
    assert "nothing changed" in run(settings, "--uninstall")
    run(settings)
    run(settings, "--uninstall")
    assert "statusLine" not in json.loads(settings.read_text())
