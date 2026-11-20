"""Format Claude Pro/Max rate limits from the Claude Code status line JSON.

Also holds the shared line layout, so every provider's columns align:
label padded to LABEL_WIDTH, percent right-aligned to 3 digits, fixed-width reset.
"""

import math
from datetime import datetime

LABEL_WIDTH = 15  # longest label is "AG Claude/GPT" (13) plus two spaces


def fmt_reset(when: datetime | None) -> str:
    """Local weekday and time, for example `Sun 18:00`; `--` (same width) when unknown."""
    if when is None:
        return "--".ljust(len(fmt_reset(datetime.now())))  # weekday width varies by locale
    return when.astimezone().strftime("%a %H:%M")


def fmt_window(label: str, used_pct: float, resets_at: datetime | None) -> str:
    return f"{label} {used_pct:3.0f}% · resets {fmt_reset(resets_at)}"


def fmt_line(label: str, body: str) -> str:
    """Label padded to LABEL_WIDTH; a longer label still keeps two spaces before the body."""
    return f"{label + '  ':<{LABEL_WIDTH}}{body}"


def fmt_windows(
    session: tuple[float, datetime | None] | None,
    week: tuple[float, datetime | None] | None,
    labels: tuple[str, str] = ("session", "week"),
) -> str:
    """`session … | week …`; a missing window keeps its column width so `|` stays aligned."""
    width = len(fmt_window("session", 0, datetime.now().astimezone()))
    parts = []
    for label, w in zip(labels, (session, week), strict=True):
        parts.append(fmt_window(label, *w) if w else f"{label} {'--':>4}".ljust(width))
    return " | ".join(parts).rstrip()


def _claude_window(window: object) -> tuple[float, datetime | None] | None:
    if not isinstance(window, dict):
        return None
    used_percentage = window.get("used_percentage")
    timestamp = window.get("resets_at")
    if type(used_percentage) not in (int, float) or (
        timestamp is not None and type(timestamp) not in (int, float)
    ):
        return None
    try:
        if not math.isfinite(used_percentage):
            return None
        reset = datetime.fromtimestamp(timestamp) if timestamp is not None else None
    except (ValueError, OverflowError, OSError):
        return None
    return used_percentage, reset


def claude_line(data: dict) -> str:
    """One line with the 5-hour and 7-day windows; each may be absent."""
    limits = data.get("rate_limits")
    if not isinstance(limits, dict):
        limits = {}
    session = _claude_window(limits.get("five_hour"))
    week = _claude_window(limits.get("seven_day"))
    if session is None and week is None:
        return fmt_line("Claude", "usage appears after the first reply")
    return fmt_line("Claude", fmt_windows(session, week))
