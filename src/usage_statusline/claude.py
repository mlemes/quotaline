"""Format Claude Pro/Max rate limits from the Claude Code status line JSON."""

from datetime import datetime


def fmt_reset(when: datetime) -> str:
    """Local weekday and time, for example `Sun 18:00`."""
    return when.astimezone().strftime("%a %H:%M")


def fmt_window(label: str, used_pct: float, resets_at: datetime) -> str:
    return f"{label} {used_pct:.0f}% · resets {fmt_reset(resets_at)}"


def claude_line(data: dict) -> str:
    """One line with the 5-hour and 7-day windows; each may be absent."""
    limits = data.get("rate_limits") or {}
    parts = []
    for key, label in (("five_hour", "session"), ("seven_day", "week")):
        w = limits.get(key)
        if w and w.get("used_percentage") is not None and w.get("resets_at"):
            resets = datetime.fromtimestamp(w["resets_at"]).astimezone()
            parts.append(fmt_window(label, w["used_percentage"], resets))
    if not parts:
        return "Claude       usage appears after the first reply"
    return "Claude       " + " | ".join(parts)
