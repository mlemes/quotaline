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
    assert f"session 24% · resets {RESET_TEXT}" in line
    assert f"week 41% · resets {RESET_TEXT}" in line


def test_only_weekly_window() -> None:
    data = {"rate_limits": {"seven_day": {"used_percentage": 5, "resets_at": RESET}}}
    line = claude_line(data)
    assert "week 5%" in line and "session" not in line


def test_no_rate_limits_yet() -> None:
    assert "after the first reply" in claude_line({})
    assert "after the first reply" in claude_line({"rate_limits": None})
