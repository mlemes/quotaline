import io
import json
from datetime import datetime

import pytest

from usage_statusline import main as m


@pytest.fixture(autouse=True)
def absent_router_config(monkeypatch):
    monkeypatch.setattr(m, "omniroute_lines", lambda: None, raising=False)
    monkeypatch.setattr(m, "opencode_line", lambda: None)


def _stdin(monkeypatch, text="{}"):
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def _natives(monkeypatch, agy="Antigravity  x", codex="Codex  y"):
    monkeypatch.setattr(m, "antigravity_line", lambda: agy)
    monkeypatch.setattr(m, "codex_line", lambda: codex)


def _claude_output(monkeypatch, capsys, **windows):
    _natives(monkeypatch, agy=None, codex=None)
    _stdin(monkeypatch, json.dumps({"rate_limits": windows}))
    m.main()
    return capsys.readouterr().out.rstrip("\n")


LIVE_CLAUDE = {"rate_limits": {"five_hour": {"used_percentage": 10, "resets_at": 4102444800}}}


def test_prints_each_live_provider(monkeypatch, capsys) -> None:
    _natives(monkeypatch)
    _stdin(monkeypatch, json.dumps(LIVE_CLAUDE))
    m.main()
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("Claude") and "10%" in lines[0]
    assert lines[1:] == ["Antigravity  x", "Codex  y"]


def test_prints_opencode_row(monkeypatch, capsys) -> None:
    _natives(monkeypatch, agy=None, codex=None)
    monkeypatch.setattr(m, "opencode_line", lambda: "OpenCode Go  z")
    _stdin(monkeypatch)
    m.main()
    assert capsys.readouterr().out == "OpenCode Go  z\n"


def test_claude_without_usage_is_hidden(monkeypatch, capsys) -> None:
    _natives(monkeypatch, codex=None)
    _stdin(monkeypatch)
    m.main()
    assert capsys.readouterr().out == "Antigravity  x\n"


@pytest.mark.parametrize("reset_fields", [{}, {"resets_at": None}], ids=["omitted", "null"])
def test_claude_usage_without_reset(monkeypatch, capsys, reset_fields) -> None:
    row = _claude_output(monkeypatch, capsys, five_hour={"used_percentage": 37, **reset_fields})
    session, _, week = row.partition(" | ")
    assert session.rstrip() == "Claude         session  37% · resets --"
    assert week == "week   --"


@pytest.mark.parametrize(
    "bad_reset", [False, "", [], {}], ids=["false", "empty-str", "list", "object"]
)
def test_claude_malformed_reset_keeps_row_and_week(monkeypatch, capsys, bad_reset) -> None:
    reset = 1738425600
    row = _claude_output(
        monkeypatch,
        capsys,
        five_hour={"used_percentage": 37, "resets_at": bad_reset},
        seven_day={"used_percentage": 41, "resets_at": reset},
    )
    session, _, week = row.partition(" | ")
    assert session.rstrip() == "Claude         session   --"
    reset_text = datetime.fromtimestamp(reset).astimezone().strftime("%a %H:%M")
    assert week == f"week  41% · resets {reset_text}"


@pytest.mark.parametrize("bad_usage", ["unknown", False], ids=["string", "false"])
def test_claude_malformed_usage_keeps_row_and_week(monkeypatch, capsys, bad_usage) -> None:
    reset = 1738425600
    row = _claude_output(
        monkeypatch,
        capsys,
        five_hour={"used_percentage": bad_usage},
        seven_day={"used_percentage": 41, "resets_at": reset},
    )
    session, _, week = row.partition(" | ")
    assert session.rstrip() == "Claude         session   --"
    reset_text = datetime.fromtimestamp(reset).astimezone().strftime("%a %H:%M")
    assert week == f"week  41% · resets {reset_text}"


def test_claude_epoch_zero_reset_is_a_real_time(monkeypatch, capsys) -> None:
    row = _claude_output(monkeypatch, capsys, five_hour={"used_percentage": 37, "resets_at": 0})
    epoch_text = datetime.fromtimestamp(0).astimezone().strftime("%a %H:%M")
    assert f"resets {epoch_text}" in row
    assert "resets --" not in row.partition(" | ")[0]


def test_claude_zero_usage_without_reset_keeps_week_aligned(monkeypatch, capsys) -> None:
    reset = 1738425600
    week = {"used_percentage": 41, "resets_at": reset}
    session = {"used_percentage": 0}
    full = _claude_output(
        monkeypatch, capsys, five_hour={**session, "resets_at": reset}, seven_day=week
    )
    row = _claude_output(monkeypatch, capsys, five_hour=session, seven_day=week)

    left, _, right = row.partition(" | ")
    assert left.rstrip() == "Claude         session   0% · resets --"
    reset_text = datetime.fromtimestamp(reset).astimezone().strftime("%a %H:%M")
    assert right == f"week  41% · resets {reset_text}"
    assert row.index("|") == full.index("|")


def test_claude_window_needs_a_reported_percentage(monkeypatch, capsys) -> None:
    reset_only = {"resets_at": 1738425600}
    row = _claude_output(
        monkeypatch, capsys, five_hour=reset_only, seven_day={"used_percentage": 41}
    )
    session, _, week = row.partition(" | ")
    assert session.rstrip() == "Claude         session   --"
    assert week == "week  41% · resets --"
    no_usage = _claude_output(
        monkeypatch, capsys, five_hour=reset_only, seven_day={"used_percentage": None}
    )
    assert no_usage == ""


@pytest.mark.parametrize("stdin", ["garbage", "null", "[]", "1"])
def test_bad_stdin_is_tolerated(monkeypatch, capsys, stdin) -> None:
    _natives(monkeypatch)
    _stdin(monkeypatch, stdin)
    m.main()
    assert capsys.readouterr().out.splitlines() == ["Antigravity  x", "Codex  y"]


@pytest.mark.parametrize("payload", [{"rate_limits": 1}, {"rate_limits": {"five_hour": 1}}])
def test_malformed_claude_input_is_hidden(monkeypatch, capsys, payload) -> None:
    _natives(monkeypatch)
    _stdin(monkeypatch, json.dumps(payload))
    m.main()
    assert capsys.readouterr().out.splitlines() == ["Antigravity  x", "Codex  y"]


@pytest.mark.parametrize(
    "row",
    [
        "Antigravity  n/a (no token, run agy to log in)",
        "AG Gemini  session 0% · stale (updated 2026-10-26 10:02)",
        "Codex  no usage yet",
        None,
    ],
)
def test_unusable_rows_are_hidden(monkeypatch, capsys, row) -> None:
    _natives(monkeypatch, agy=row, codex=row)
    _stdin(monkeypatch)
    m.main()
    assert capsys.readouterr().out == ""


def test_provider_failure_does_not_hide_codex(monkeypatch, capsys) -> None:
    def broken():
        raise OSError("cache unavailable")

    monkeypatch.setattr(m, "antigravity_line", broken)
    monkeypatch.setattr(m, "codex_line", lambda: "Codex  y")
    _stdin(monkeypatch)
    m.main()
    assert capsys.readouterr().out == "Codex  y\n"


def test_router_mode_shows_live_rows_only_and_skips_native(monkeypatch, capsys) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("router mode touched a native source or stdin")

    router = (
        "OmniRoute      upstream age unknown\n"
        "Codex          routed usage\n"
        "Claude         session 5% · stale (received 2026-10-26 03:46)\n"
        "AG Gemini      n/a (quota unavailable or inconsistent)"
    )
    monkeypatch.setattr(m, "omniroute_lines", lambda: router)
    monkeypatch.setattr(m, "claude_line", forbidden)
    monkeypatch.setattr(m, "antigravity_line", forbidden)
    monkeypatch.setattr(m, "codex_line", forbidden)
    monkeypatch.setattr("sys.stdin", type("S", (), {"read": forbidden, "readline": forbidden})())
    m.main()
    assert capsys.readouterr().out.splitlines() == [
        "OmniRoute      upstream age unknown",
        "Codex          routed usage",
    ]


@pytest.mark.parametrize("failure", ["fetch", "exception", "no_live_rows"])
def test_router_without_live_rows_falls_back_to_native(monkeypatch, capsys, failure) -> None:
    def router():
        if failure == "exception":
            raise RuntimeError("private-key-must-not-leak")
        if failure == "fetch":
            return (
                "OmniRoute      upstream age unknown\n"
                "OmniRoute      n/a (fetch failed)\n"
                "Codex          session 1% · stale (received 2026-10-26 10:02)"
            )
        return (
            "OmniRoute      upstream age unknown\n"
            "Codex          n/a (selected connection unavailable)"
        )

    monkeypatch.setattr(m, "omniroute_lines", router)
    _natives(monkeypatch)
    _stdin(monkeypatch)
    m.main()
    out = capsys.readouterr().out
    assert out.splitlines() == ["Antigravity  x", "Codex  y"]
    assert "OmniRoute" not in out and "private-key" not in out
