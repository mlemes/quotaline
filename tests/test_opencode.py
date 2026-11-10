import json
from pathlib import Path

import pytest

from usage_statusline.opencode import opencode_line, parse_usage, read_key

PAYLOAD = {
    "usage": {
        p: {"status": "ok", "percent": pc, "resetsAt": "2026-11-09T18:00:00Z"}
        for p, pc in (("rolling", 12), ("weekly", 34.5), ("monthly", 5))
    }
}


def test_parse_usage() -> None:
    u = parse_usage(json.dumps(PAYLOAD))
    assert u["rolling"][0] == 12 and u["weekly"][0] == 34.5


@pytest.mark.parametrize("bad", ["{}", '{"usage": {"rolling": 1}}', "nope"])
def test_parse_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_usage(bad)


def test_read_key_missing(tmp_path: Path) -> None:
    f = tmp_path / "auth.json"
    assert read_key((f,)) is None
    f.write_text(json.dumps({"opencode-go": {"type": "api_key", "key": "k"}}))
    assert read_key((tmp_path / "x", f)) == "k"


def test_absent_returns_none(tmp_path: Path) -> None:
    assert opencode_line(tmp_path / "c.json", (tmp_path / "nope",)) is None


def test_line_and_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({"opencode-go": {"key": "k"}}))
    calls = []

    def fake(key: str):
        calls.append(key)
        return parse_usage(json.dumps(PAYLOAD))

    monkeypatch.setattr("usage_statusline.opencode.fetch_usage", fake)
    cache = tmp_path / "c.json"
    line = opencode_line(cache, (auth,), now=1000.0)
    assert line.startswith("OpenCode Go") and "session  12%" in line and "week  34%" in line
    assert opencode_line(cache, (auth,), now=1010.0) == line and calls == ["k"]


def test_failure_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({"opencode-go": {"key": "k"}}))

    def boom(key: str):
        raise OSError

    monkeypatch.setattr("usage_statusline.opencode.fetch_usage", boom)
    assert "n/a (OSError)" in opencode_line(tmp_path / "c.json", (auth,), now=1.0)
