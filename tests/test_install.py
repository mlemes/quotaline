import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "install.sh"


def run(settings: Path, *args: str) -> str:
    env = {**os.environ, "CLAUDE_SETTINGS": str(settings)}
    return subprocess.run(
        # --no-agy: tests must never touch the real keyring
        ["bash", str(SCRIPT), "--no-agy", *args],
        env=env,
        capture_output=True,
        text=True,
        check=True,
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


def test_unknown_flag_fails(tmp_path: Path) -> None:
    env = {**os.environ, "CLAUDE_SETTINGS": str(tmp_path / "s.json")}
    r = subprocess.run(["bash", str(SCRIPT), "--bogus"], env=env, capture_output=True, text=True)
    assert r.returncode == 2 and "usage:" in r.stderr
    assert not (tmp_path / "s.json").exists()


def test_uninstall_removes_only_our_status_line(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"statusLine": {"type": "command", "command": "other"}}))
    assert "nothing changed" in run(settings, "--uninstall")
    run(settings)
    run(settings, "--uninstall")
    assert "statusLine" not in json.loads(settings.read_text())
