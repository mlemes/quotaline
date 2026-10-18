import io
import json

import pytest

from usage_statusline import main as m


def test_main_prints_two_lines(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(m, "antigravity_line", lambda: "Antigravity  x")
    monkeypatch.setattr(m, "codex_line", lambda: None)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({})))
    m.main()
    assert capsys.readouterr().out.splitlines()[1:] == ["Antigravity  x"]


def test_main_prints_codex_line(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(m, "antigravity_line", lambda: "Antigravity  x")
    monkeypatch.setattr(m, "codex_line", lambda: "Codex  y")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({})))
    m.main()
    assert capsys.readouterr().out.splitlines()[1:] == ["Antigravity  x", "Codex  y"]


def test_main_tolerates_bad_stdin(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(m, "antigravity_line", lambda: "Antigravity  x")
    monkeypatch.setattr(m, "codex_line", lambda: None)
    monkeypatch.setattr("sys.stdin", io.StringIO("garbage"))
    m.main()
    assert capsys.readouterr().out.startswith("Claude")


def test_provider_failure_does_not_hide_codex(monkeypatch, capsys):
    def broken():
        raise OSError("cache unavailable")

    monkeypatch.setattr(m, "antigravity_line", broken)
    monkeypatch.setattr(m, "codex_line", lambda: "Codex  y")
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    m.main()
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("Claude")
    assert "n/a" in lines[1]
    assert lines[2] == "Codex  y"
