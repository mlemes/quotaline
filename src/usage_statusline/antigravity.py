"""Antigravity (agy) quota line, fetched from Google's Code Assist API and cached.

The access token comes from a command you configure (see README), because
agy keeps its OAuth token in the system keyring.
"""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from usage_statusline.claude import fmt_window

# Endpoint agy itself calls (seen in ~/.gemini/antigravity-cli/cli.log).
URL = "https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels"
CACHE_TTL = 60  # seconds; the status line runs far more often than this
TIMEOUT = 2  # seconds; never stall the status line for long
LABEL = "Antigravity  "
CONFIG = Path.home() / ".config" / "usage-statusline" / "agy_token_cmd"
CACHE = Path.home() / ".cache" / "usage-statusline" / "antigravity.json"


def family(model_id: str) -> str | None:
    """Quota group a model belongs to; None for models we don't show."""
    m = model_id.lower()
    if m.startswith("claude"):
        return "Claude"
    if m.startswith("gemini") and "flash" in m:
        return "Flash"
    if m.startswith("gemini") and "pro" in m:
        return "Pro"
    return None


def parse_quota(resp: dict) -> dict[str, tuple[float, datetime]]:
    """Family -> (used %, reset time), keeping the most-used model per family."""
    out: dict[str, tuple[float, datetime]] = {}
    for model_id, info in (resp.get("models") or {}).items():
        q = info.get("quotaInfo") or {}
        fam = family(model_id)
        if fam is None or "resetTime" not in q:
            continue
        used = 100 * (1 - q.get("remainingFraction", 0))
        reset = datetime.fromisoformat(q["resetTime"].replace("Z", "+00:00"))
        if fam not in out or used > out[fam][0]:
            out[fam] = (used, reset)
    return out


def format_line(quota: dict[str, tuple[float, datetime]]) -> str:
    if not quota:
        return LABEL + "no quota data"
    order = [f for f in ("Flash", "Pro", "Claude") if f in quota]
    return LABEL + " | ".join(fmt_window(f, *quota[f]) for f in order)


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
        return LABEL + "n/a (no token command, see README)"
    try:
        token = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=TIMEOUT
        ).stdout.strip()
        if not token:
            return LABEL + "n/a (no token, run agy to log in)"
        req = urllib.request.Request(
            URL,
            data=b"{}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return format_line(parse_quota(json.load(r)))
    except urllib.error.HTTPError as e:
        return LABEL + f"n/a (HTTP {e.code}, run agy to refresh login)"
    except (OSError, ValueError, subprocess.SubprocessError):
        return LABEL + "n/a (fetch failed)"


def antigravity_line(cache: Path = CACHE, now: float | None = None) -> str:
    """Cached line; refetches at most once per CACHE_TTL, errors included."""
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
