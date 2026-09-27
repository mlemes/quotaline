from datetime import datetime

from usage_statusline.claude import claude_line

RESET = 1738425600
RESET_TEXT = datetime.fromtimestamp(RESET).astimezone().strftime("%a %H:%M")


def test_both_windows() -> None:
    data = {
        "rate_limits": {
            "five_hour": {"used_percentage": 23.5, "resets_at": RESET},
            "seven_day": {"used_percentage": 41.2, "resets_at": RESET},
        }
    }
    line = claude_line(data)
    r = RESET_TEXT
    assert line == f"Claude         session  24% · resets {r} | week  41% · resets {r}"


def test_only_weekly_window() -> None:
    data = {"rate_limits": {"seven_day": {"used_percentage": 5, "resets_at": RESET}}}
    line = claude_line(data)
    week = data["rate_limits"]["seven_day"]
    full = claude_line({"rate_limits": {"five_hour": week, "seven_day": week}})
    assert "week   5%" in line and "session   --" in line
    assert line.index("|") == full.index("|")  # a missing window keeps its column width


def test_no_rate_limits_yet() -> None:
    assert "after the first reply" in claude_line({})
    assert "after the first reply" in claude_line({"rate_limits": None})


def test_claude_and_antigravity_lines_align() -> None:
    from datetime import UTC

    from usage_statusline.antigravity import format_lines

    when = datetime.fromtimestamp(RESET, UTC)
    w = {"used_percentage": 100, "resets_at": RESET}
    claude = claude_line({"rate_limits": {"five_hour": w, "seven_day": w}})
    ag = format_lines([("AG Claude/GPT", (0, when), (7, when))])
    for mark in ("session", "·", "|", "week"):
        assert claude.index(mark) == ag.index(mark), mark
