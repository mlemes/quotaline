"""OpenCode Go usage from `https://opencode.ai/inference/go/v1/usage`, cached.

The API key comes from the `opencode-go` entry of Pi's or OpenCode's `auth.json`. The response
holds `rolling` (5 hours), `weekly` and `monthly` periods; the line shows the first two.
"""

import json
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from usage_statusline.claude import fmt_line, fmt_windows

URL = "https://opencode.ai/inference/go/v1/usage"
AUTH_FILES = (
    Path.home() / ".pi" / "agent" / "auth.json",
    Path.home() / ".local" / "share" / "opencode" / "auth.json",
)
CACHE = Path.home() / ".cache" / "usage-statusline" / "opencode.json"
CACHE_TTL = 60  # seconds; the status line runs far more often than this
TIMEOUT = 5
MAX_BODY = 1024 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # The Bearer key must not follow a redirect.


def read_key(auth_files: tuple[Path, ...] = AUTH_FILES) -> str | None:
    """API key of the `opencode-go` entry, or None when Go is not set up."""
    for path in auth_files:
        try:
            entry = json.loads(path.read_text())["opencode-go"]
            if isinstance(entry, dict) and isinstance(entry.get("key"), str) and entry["key"]:
                return entry["key"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def parse_usage(payload: bytes | str) -> dict[str, tuple[float, datetime | None]]:
    """`{period: (percent, resets_at)}`; raises ValueError on an unexpected shape."""
    try:
        usage = json.loads(payload)["usage"]
        result = {}
        for name in ("rolling", "weekly", "monthly"):
            w = usage[name]
            if w["status"] != "ok" or isinstance(w["percent"], bool):
                raise ValueError("period not ok")
            percent = float(w["percent"])
            reset = datetime.fromisoformat(w["resetsAt"].replace("Z", "+00:00"))
            if not 0 <= percent <= 100:
                raise ValueError("percent out of range")
            result[name] = (percent, reset)
        return result
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError("invalid Go usage response") from e


def fetch_usage(key: str) -> dict[str, tuple[float, datetime | None]]:
    request = urllib.request.Request(
        URL, headers={"Authorization": f"Bearer {key}", "User-Agent": "usage-statusline/1"}
    )
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=TIMEOUT) as response:
        body = response.read(MAX_BODY + 1)
    if len(body) > MAX_BODY:
        raise ValueError("response too large")
    return parse_usage(body)


def format_line(usage: dict[str, tuple[float, datetime | None]]) -> str:
    return fmt_line("OpenCode Go", fmt_windows(usage["rolling"], usage["weekly"]))


def opencode_line(
    cache: Path = CACHE,
    auth_files: tuple[Path, ...] = AUTH_FILES,
    now: float | None = None,
) -> str | None:
    """None when Go is not set up; an `n/a (...)` row on failure; never raises."""
    now = time.time() if now is None else now
    try:
        c = json.loads(cache.read_text())
        if 0 <= now - c["fetched_at"] < CACHE_TTL:
            return c["line"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        key = read_key(auth_files)
        if key is None:
            return None
        line = format_line(fetch_usage(key))
    except Exception as e:  # noqa: BLE001
        return fmt_line("OpenCode Go", f"n/a ({type(e).__name__})")
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=cache.parent, delete=False) as f:
            json.dump({"fetched_at": now, "line": line}, f)
        Path(f.name).replace(cache)
    except OSError:
        pass
    return line
