from usage_statusline.settings_entry import update

CMD = "PYTHONPATH=/x python3 -m usage_statusline"


def test_install_keeps_other_keys_and_replaces_another_status_line() -> None:
    s = {"model": "opus", "statusLine": {"type": "command", "command": "other"}}
    assert "Replaced the statusLine command other" in update(s, CMD, "install")
    assert s == {
        "model": "opus",
        "statusLine": {"type": "command", "command": CMD, "refreshInterval": 60},
    }


def test_uninstall_removes_only_our_command() -> None:
    other = {"statusLine": {"type": "command", "command": "other"}}
    assert update(other, CMD, "--uninstall") is None
    assert other["statusLine"]["command"] == "other"
    ours = {"statusLine": {"command": CMD}}
    assert update(ours, CMD, "--uninstall")
    assert ours == {}
