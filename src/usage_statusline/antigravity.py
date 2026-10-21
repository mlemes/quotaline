"""Antigravity (agy) quota lines, one per quota group, from Google's Code Assist API, cached.

The access token comes from a command you configure (see README), because
agy keeps its OAuth token in the system keyring.
"""

import base64
import json
import math
import os
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from usage_statusline.claude import fmt_line, fmt_window, fmt_windows

# agy calls this too; it returns quota groups, each with a 5h and a weekly bucket.
# Reviewer note: the token sent here is agy's Google OAuth token, and this Google host is its
# issuer. Quota requests stay on this host. See README "Notes for reviewers".
URL = "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary"
USER_AGENT = "antigravity/cli/1.4.2"
CACHE_TTL = 60  # seconds; the status line runs far more often than this
TIMEOUT = 2  # seconds per token lookup or quota request
REFRESH_TIMEOUT = 10  # seconds; only after HTTP 401
LABEL = "Antigravity"
# Short labels by bucketId prefix; unknown groups fall back to the API displayName.
GROUP_LABELS = {"gemini": "AG Gemini", "gemini-argon": "AG Argon", "3p": "AG Claude/GPT"}
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
                fraction = b.get("remainingFraction", 0)  # missing means exhausted
                if not isinstance(fraction, (int, float)) or isinstance(fraction, bool):
                    continue
                if not math.isfinite(fraction) or not 0 <= fraction <= 1:
                    continue
                used = 100 * (1 - fraction)
                reset = datetime.fromisoformat(b["resetTime"].replace("Z", "+00:00"))
                windows[b["window"]] = (used, reset)
        bucket_id = buckets[0].get("bucketId", "") if buckets else ""
        prefix = (
            "gemini-argon" if bucket_id.startswith("gemini-argon-") else bucket_id.split("-")[0]
        )
        label = GROUP_LABELS.get(prefix) or g.get("displayName") or "AG ?"
        out.append((label, windows.get("5h"), windows.get("weekly")))
    return out


def parse_models(resp: dict) -> list[str]:
    """Gemini model quota, deduplicating only identical fractions and reset times."""
    quotas = {}
    for model_id, model in (resp.get("models") or {}).items():
        name = model.get("displayName") or model_id
        if "gemini" not in (model_id + " " + name).lower() or model.get("isInternal"):
            continue
        quota = model.get("quotaInfo") or {}
        fraction, reset = quota.get("remainingFraction"), quota.get("resetTime")
        if not isinstance(fraction, (int, float)) or isinstance(fraction, bool):
            continue
        if not math.isfinite(fraction) or not 0 <= fraction <= 1 or not reset:
            continue
        when = datetime.fromisoformat(reset.replace("Z", "+00:00"))
        quotas.setdefault((fraction, when), name)
    return [
        fmt_line(
            "AG Gemini" if len(quotas) == 1 else f"AG {name}",
            fmt_window("quota", 100 * (1 - fraction), reset),
        )
        for (fraction, reset), name in quotas.items()
    ]


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


def refresh_login() -> bool:
    """Let agy own OAuth refresh; bound startup and terminate its process group."""
    agy = shutil.which("agy")
    if not agy:
        return False
    with subprocess.Popen(
        [agy, "models"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    ) as process:
        try:
            return process.wait(timeout=REFRESH_TIMEOUT) == 0
        except subprocess.TimeoutExpired:
            return False
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def fetch_line() -> str:
    try:
        cmd = token_cmd()
        if not cmd or not (argv := shlex.split(cmd)):
            return fmt_line(LABEL, "n/a (no token command, see README)")

        def read_token():
            # No shell: the saved command is one program plus its arguments. The token it prints
            # goes only to URL, and the response is parsed as JSON, never run.
            result = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT)
            return extract_token(result.stdout) if result.returncode == 0 else ""

        token = read_token()
        if not token:
            return fmt_line(LABEL, "n/a (no token, run agy to log in)")
        refreshed = False

        def request(endpoint):
            nonlocal token, refreshed
            for attempt in range(2):
                # Google returns 403 for the default Python-urllib User-Agent (seen 2026-09-27)
                # The CLI User-Agent exposes Gemini and Argon groups omitted by bare antigravity.
                req = urllib.request.Request(
                    URL.replace("retrieveUserQuotaSummary", endpoint),
                    data=b"{}",
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": USER_AGENT,
                    },
                )
                req.add_unredirected_header("Authorization", f"Bearer {token}")
                try:
                    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                        return json.load(response)
                except urllib.error.HTTPError as error:
                    if error.code != 401 or refreshed or attempt:
                        raise
                    refreshed = True
                    if not refresh_login() or not (token := read_token()):
                        raise

        def error_line(label, error):
            detail = (
                f"HTTP {error.code}"
                if isinstance(error, urllib.error.HTTPError)
                else "fetch failed"
            )
            return fmt_line(label, f"n/a ({detail}; run agy to check login)")

        lines = []
        try:
            groups = parse_summary(request("retrieveUserQuotaSummary"))
            lines = format_lines(groups).splitlines() if groups else []
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            subprocess.SubprocessError,
        ) as error:
            groups = []
            lines.append(error_line(LABEL, error))
        if not any(label == "AG Gemini" for label, _, _ in groups):
            try:
                models = parse_models(request("fetchAvailableModels"))
                lines.extend(models or [fmt_line("AG Gemini", "n/a (no quota data)")])
            except (
                OSError,
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                subprocess.SubprocessError,
            ) as error:
                lines.append(error_line("AG Gemini", error))
        return "\n".join(lines)
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
        return fmt_line(LABEL, "n/a (fetch failed)")


def antigravity_line(cache: Path = CACHE, now: float | None = None) -> str:
    """Throttle fetches, retaining timestamped successful rows across partial failures."""
    now = time.time() if now is None else now
    previous = {}
    try:
        c = json.loads(cache.read_text())
        if not isinstance(c["line"], str):
            raise ValueError("invalid cached line")
        if 0 <= now - c["fetched_at"] < CACHE_TTL:
            return c["line"]
        previous = c.get("successful", {})
        if not isinstance(previous, dict):
            previous = {}
        if not previous and "n/a" not in c["line"] and "stale" not in c["line"]:
            previous = {
                row.split("  ", 1)[0]: [row, c["fetched_at"]] for row in c["line"].splitlines()
            }
    except (OSError, ValueError, KeyError, TypeError):
        pass
    fresh = fetch_line()
    errors = [row for row in fresh.splitlines() if "n/a" in row or "no quota data" in row]
    successful = {}
    rows = []
    for row in fresh.splitlines():
        if row not in errors:
            label = row.split("  ", 1)[0]
            successful[label] = [row, now]
            rows.append(row)
    if errors:
        for label, value in previous.items():
            if label in successful:
                continue
            try:
                row, observed = value
                stamp = datetime.fromtimestamp(observed).astimezone().strftime("%Y-%m-%d %H:%M")
                if not isinstance(row, str):
                    continue
                rows.append(f"{row} · stale (updated {stamp})")
                successful[label] = [row, observed]
            except (TypeError, ValueError, OverflowError, OSError):
                continue
        rows.extend(errors)
    line = "\n".join(rows)
    temporary = None
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=cache.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump({"fetched_at": now, "line": line, "successful": successful}, file)
        temporary.replace(cache)
    except OSError:
        pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return line
