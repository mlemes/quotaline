import io
import json

import pytest

from usage_statusline import main as m
from usage_statusline.claude import fmt_line


@pytest.fixture(autouse=True)
def absent_router_config(monkeypatch):
    monkeypatch.setattr(m, "omniroute_lines", lambda: None, raising=False)


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


@pytest.mark.parametrize("stdin", ["null", "[]", "1"])
def test_main_tolerates_non_object_stdin(monkeypatch: pytest.MonkeyPatch, capsys, stdin) -> None:
    monkeypatch.setattr(m, "antigravity_line", lambda: "Antigravity  x")
    monkeypatch.setattr(m, "codex_line", lambda: "Codex  y")
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    m.main()
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("Claude")
    assert lines[1:] == ["Antigravity  x", "Codex  y"]


@pytest.mark.parametrize(
    "payload",
    [
        {"rate_limits": 1},
        {"rate_limits": {"five_hour": {"used_percentage": 10, "resets_at": "x"}}},
    ],
)
def test_malformed_claude_input_is_na_and_keeps_other_lines(monkeypatch, capsys, payload):
    monkeypatch.setattr(m, "antigravity_line", lambda: "Antigravity  x")
    monkeypatch.setattr(m, "codex_line", lambda: "Codex  y")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    m.main()
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("Claude") and "n/a" in lines[0]
    assert lines[1:] == ["Antigravity  x", "Codex  y"]


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


@pytest.mark.parametrize("unexpected_error", [False, True])
def test_router_mode_never_reads_stdin_or_calls_native(monkeypatch, capsys, unexpected_error):
    def forbidden(*args, **kwargs):
        pytest.fail("router mode touched a native source or stdin")

    class UnreadableInput:
        read = forbidden
        readline = forbidden

    def router():
        if unexpected_error:
            raise RuntimeError("private-key-must-not-leak")
        return "OmniRoute      upstream age unknown\nCodex          routed usage"

    monkeypatch.setattr(m, "omniroute_lines", router)
    monkeypatch.setattr(m, "claude_line", forbidden)
    monkeypatch.setattr(m, "antigravity_line", forbidden)
    monkeypatch.setattr(m, "codex_line", forbidden)
    monkeypatch.setattr("sys.stdin", UnreadableInput())
    m.main()
    expected = fmt_line("OmniRoute", "n/a (fetch failed)") if unexpected_error else router()
    assert capsys.readouterr().out == expected + "\n"
