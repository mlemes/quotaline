"""Antigravity (agy) quota lines, one per quota group, from Google's Code Assist API, cached.

The access token comes from a command you configure (see README), because
agy keeps its OAuth token in the system keyring.
"""

import base64
import json
import os
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from usage_statusline.claude import fmt_line, fmt_windows

# agy calls this too; it returns quota groups, each with a 5h and a weekly bucket.
URL = "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary"
CACHE_TTL = 60  # seconds; the status line runs far more often than this
TIMEOUT = 2  # seconds; never stall the status line for long
LABEL = "Antigravity"
# Short labels by bucketId prefix; unknown groups fall back to the API displayName.
GROUP_LABELS = {"gemini": "AG Gemini", "3p": "AG Claude/GPT"}
CONFIG = Path.home() / ".config" / "usage-statusline" / "agy_token_cmd"
CACHE = Path.home() / ".cache" / "usage-statusline" / "antigravity.json"

Window = tuple[float, datetime]


def parse_summary(resp: dict) -> list[tuple[str, Window | None, Window | None]]:
    """(label, 5h window, weekly window) per quota group, in API order."""
    out = []
    for g in resp.get("groups") or []:
        buckets = g.get("buckets") or []
        windows: dict[str, Window] = {}
        for b in buckets:
            if b.get("window") in ("5h", "weekly") and b.get("resetTime"):
                used = 100 * (1 - b.get("remainingFraction", 0))  # missing means exhausted
                reset = datetime.fromisoformat(b["resetTime"].replace("Z", "+00:00"))
                windows[b["window"]] = (used, reset)
        prefix = (buckets[0].get("bucketId", "") if buckets else "").split("-")[0]
        label = GROUP_LABELS.get(prefix) or g.get("displayName") or "AG ?"
        out.append((label, windows.get("5h"), windows.get("weekly")))
    return out


def format_lines(groups: list[tuple[str, Window | None, Window | None]]) -> str:
    if not groups:
        return fmt_line(LABEL, "no quota data")
    return "\n".join(fmt_line(label, fmt_windows(s, w)) for label, s, w in groups)


def extract_token(raw: str) -> str:
    """Access token from a keyring secret: plain, oauth2 JSON, or go-keyring base64.

    agy stores {"auth_method", "id_token", "token": {oauth2 token}} (seen 2026-09-27).
    """
    raw = raw.strip()
    if raw.startswith("go-keyring-base64:"):
        raw = base64.b64decode(raw.removeprefix("go-keyring-base64:")).decode().strip()
    if raw.startswith("{"):
        d = json.loads(raw)
        if isinstance(d.get("token"), dict):
            d = d["token"]
        return d.get("access_token") or d.get("accessToken") or ""
    return raw


def token_cmd() -> str | None:
    cmd = os.environ.get("USAGE_STATUSLINE_AGY_TOKEN_CMD")
    if cmd:
        return cmd
    if CONFIG.exists():
        return CONFIG.read_text().strip() or None
    return None


def fetch_line() -> str:
    cmd = token_cmd()
    if not cmd:
        return fmt_line(LABEL, "n/a (no token command, see README)")
    try:
        # no shell: the saved command is one program plus its arguments
        argv = shlex.split(cmd)
        if not argv:
            return fmt_line(LABEL, "n/a (no token command, see README)")
        token = extract_token(
            subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT).stdout
        )
        if not token:
            return fmt_line(LABEL, "n/a (no token, run agy to log in)")
        req = urllib.request.Request(
            URL,
            data=b"{}",
            # Google returns 403 for the default Python-urllib User-Agent (seen 2026-09-27)
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "antigravity",
            },
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return format_lines(parse_summary(json.load(r)))
    except urllib.error.HTTPError as e:
        return fmt_line(LABEL, f"n/a (HTTP {e.code}, run agy to refresh login)")
    except (OSError, ValueError, subprocess.SubprocessError):
        return fmt_line(LABEL, "n/a (fetch failed)")


def antigravity_line(cache: Path = CACHE, now: float | None = None) -> str:
    """Cached lines; refetches at most once per CACHE_TTL, errors included."""
    now = time.time() if now is None else now
    try:
        c = json.loads(cache.read_text())
        if now - c["fetched_at"] < CACHE_TTL:
            return c["line"]
    except (OSError, ValueError, KeyError):
        pass
    line = fetch_line()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"fetched_at": now, "line": line}))
    return line
