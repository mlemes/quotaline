"""Format Claude Pro/Max rate limits from the Claude Code status line JSON.

Also holds the shared line layout, so every provider's columns align:
label padded to LABEL_WIDTH, percent right-aligned to 3 digits, fixed-width reset.
"""

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
    return f"{label:<{LABEL_WIDTH}}{body}"


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


def claude_line(data: dict) -> str:
    """One line with the 5-hour and 7-day windows; each may be absent."""
    limits = data.get("rate_limits") or {}
    windows = []
    for key in ("five_hour", "seven_day"):
        w = limits.get(key)
        if w and w.get("used_percentage") is not None and w.get("resets_at"):
            windows.append((w["used_percentage"], datetime.fromtimestamp(w["resets_at"])))
        else:
            windows.append(None)
    if windows == [None, None]:
        return fmt_line("Claude", "usage appears after the first reply")
    return fmt_line("Claude", fmt_windows(*windows))
