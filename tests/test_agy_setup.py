import base64
import json
import shlex
from pathlib import Path

import pytest

from usage_statusline import agy_setup as setup
from usage_statusline import antigravity as ag

ROOT = "/org/freedesktop/secrets"
LOGIN = f"{ROOT}/collection/login"
# Fake keyring: path -> (label, attributes, secret). Shapes match `gdbus call` output.
ITEMS = {
    f"{LOGIN}/1": ("Antigravity Safe Storage", {"application": "antigravity"}, "chromium-key"),
    f"{LOGIN}/2": (
        "Password for 'me@x.com' on 'antigravity-cli'",
        {"service": "antigravity-cli", "username": "me@x.com"},
        json.dumps({"access_token": "ya29.abc", "refresh_token": "r"}),
    ),
    f"{LOGIN}/3": ("Wi-Fi", {"ssid": "home"}, "pw"),
}


def fake_run(items: dict) -> setup.Run:
    def run(args: list[str]) -> str:
        if args[0] == "secret-tool":
            for _, attrs, secret in items.values():
                if args == shlex.split(setup.lookup_cmd(attrs)):
                    return secret
            return ""
        path, name = args[args.index("-o") + 1], args[-1]
        if name == "Collections":
            return f"(<[objectpath '{LOGIN}']>,)\n"
        if name == "Items":
            return "(<[objectpath " + ", ".join(f"'{p}'" for p in items) + "]>,)\n"
        label, attrs, _ = items[path]
        if name == "Label":
            return f"(<'{label}'>,)\n"
        return "(<{" + ", ".join(f"'{k}': '{v}'" for k, v in attrs.items()) + "}>,)\n"

    return run


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(ag, "CONFIG", tmp_path / "cfg" / "agy_token_cmd")
    monkeypatch.setattr(ag, "CACHE", tmp_path / "cache.json")
    monkeypatch.setattr(ag, "antigravity_line", lambda: "Antigravity  ok")
    return tmp_path


def always(_: str) -> str:
    return "/usr/bin/x"


def test_list_entries_parses_gdbus_output() -> None:
    entries = setup.list_entries(fake_run(ITEMS))
    assert entries[1] == (ITEMS[f"{LOGIN}/2"][0], ITEMS[f"{LOGIN}/2"][1])
    assert len(entries) == 3


def test_candidates_skip_safe_storage_and_unrelated() -> None:
    found = setup.candidates(setup.list_entries(fake_run(ITEMS)))
    assert [attrs["service"] for _, attrs in found] == ["antigravity-cli"]


def test_lookup_cmd_quotes_values() -> None:
    assert setup.lookup_cmd({"a b": "c'd"}) == "secret-tool lookup 'a b' 'c'\"'\"'d'"


def test_single_match_writes_config(home: Path, capsys) -> None:
    ag.CACHE.write_text("stale")
    assert setup.main([], fake_run(ITEMS), always) == 0
    assert ag.CONFIG.read_text().strip() == setup.lookup_cmd(ITEMS[f"{LOGIN}/2"][1])
    assert not ag.CACHE.exists()
    out = capsys.readouterr().out
    assert "Antigravity  ok" in out and "ya29" not in out  # never print the token


def test_several_matches_list_labels_and_stop(home: Path, capsys) -> None:
    items = {**ITEMS, f"{LOGIN}/4": ("agy backup", {"service": "agy"}, "ya29.def")}
    assert setup.main([], fake_run(items), always) == 1
    out = capsys.readouterr().out
    assert "found 2" in out and "ya29" not in out
    assert not ag.CONFIG.exists()
    assert setup.main(["--agy-entry", "2"], fake_run(items), always) == 0
    assert ag.CONFIG.read_text().strip() == "secret-tool lookup service agy"


def test_entry_out_of_range(home: Path) -> None:
    assert setup.main(["--agy-entry", "5"], fake_run(ITEMS), always) == 1


def test_missing_secret_tool(home: Path, capsys) -> None:
    assert setup.main([], fake_run(ITEMS), lambda t: None) == 1
    assert "apt install libsecret-tools" in capsys.readouterr().out


def test_entry_without_token(home: Path) -> None:
    items = {f"{LOGIN}/2": ("agy", {"service": "agy"}, "")}
    assert setup.main([], fake_run(items), always) == 1
    assert not ag.CONFIG.exists()


@pytest.mark.parametrize(
    "raw",
    [
        "ya29.abc\n",
        json.dumps({"access_token": "ya29.abc"}),
        # agy's real layout
        json.dumps({"auth_method": "consumer", "token": {"access_token": "ya29.abc"}}),
        "go-keyring-base64:" + base64.b64encode(b'{"access_token": "ya29.abc"}').decode(),
    ],
)
def test_extract_token_formats(raw: str) -> None:
    assert ag.extract_token(raw) == "ya29.abc"
