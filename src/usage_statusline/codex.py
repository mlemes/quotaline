"""Codex usage from the newest rate limit record in its session transcripts.

Codex writes `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-*.jsonl`; token_count events carry
`rate_limits`. Only the tail of the newest files is read, since transcripts reach several MB.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from usage_statusline.claude import fmt_line, fmt_windows

SESSIONS = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "sessions"
TAIL = 256 * 1024  # bytes read from the end of a file
DAYS = 7  # newest day folders searched
FILES = 3  # newest files checked


def _tail_lines(path: Path) -> list[str]:
    with path.open("rb") as f:
        size = f.seek(0, os.SEEK_END)
        f.seek(max(0, size - TAIL))
        data = f.read()
    lines = data.decode("utf-8", errors="replace").splitlines()
    return lines[1:] if size > TAIL else lines


def _normalize(limits: dict, ts: str | None) -> dict:
    """Give each window an epoch `resets_at`, converting older `resets_in_seconds`."""
    for key in ("primary", "secondary"):
        w = limits.get(key)
        if (
            isinstance(w, dict)
            and w.get("resets_at") is None
            and w.get("resets_in_seconds") is not None
        ):
            base = datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
            w["resets_at"] = (base + timedelta(seconds=w["resets_in_seconds"])).timestamp()
    return limits


def _from_file(path: Path) -> dict | None:
    for line in reversed(_tail_lines(path)):
        try:
            ev = json.loads(line)
            p = ev["payload"]
            limits = p["rate_limits"]
            if p["type"] == "token_count" and limits and limits.get("limit_id", "codex") == "codex":
                return _normalize(limits, ev.get("timestamp"))
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    return None


def latest_rate_limits(sessions: Path = SESSIONS) -> dict | None:
    """`rate_limits` of the newest usable token_count event, or None."""
    days = sorted(
        (d for d in sessions.glob("*/*/*") if d.is_dir()), key=lambda d: d.parts[-3:], reverse=True
    )[:DAYS]
    files = []
    for d in days:
        for f in d.glob("rollout-*.jsonl"):
            try:
                files.append((f.stat().st_mtime, f))
            except OSError:
                pass
    for _, f in sorted(files, reverse=True)[:FILES]:
        try:
            if limits := _from_file(f):
                return limits
        except (OSError, ValueError):
            pass
    return None


def _window(w: dict | None, now: float) -> tuple[float, datetime | None] | None:
    if not w or w.get("used_percent") is None or w.get("resets_at") is None:
        return None
    if w["resets_at"] < now:  # reset since Codex last ran
        return (0, None)
    return (w["used_percent"], datetime.fromtimestamp(w["resets_at"]))


def _label(w: dict) -> str:
    m = w["window_minutes"]
    return "week" if m == 10080 else f"{m // 1440}d"


def codex_line(sessions: Path = SESSIONS, now: float | None = None) -> str | None:
    """None when Codex is not installed (no sessions dir); never raises."""
    try:
        if not sessions.is_dir():
            return None
        limits = latest_rate_limits(sessions)
        if not limits:
            return fmt_line("Codex", "no usage yet")
        now = time.time() if now is None else now
        slots: list[tuple[float, datetime | None] | None] = [None, None]
        second = "week"
        for w in (limits.get("primary"), limits.get("secondary")):
            if not w or w.get("window_minutes") is None:
                continue
            i = 0 if w["window_minutes"] <= 1440 else 1
            slots[i] = _window(w, now)
            if i:
                second = _label(w)
        return fmt_line("Codex", fmt_windows(*slots, labels=("session", second.ljust(4))))
    except Exception as e:  # noqa: BLE001
        return fmt_line("Codex", f"n/a ({type(e).__name__})")
