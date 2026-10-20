"""Optional OmniRoute quota source: explicit account mapping, one local authenticated GET."""

import hashlib
import json
import math
import os
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from usage_statusline.claude import fmt_line, fmt_windows

CONFIG = Path.home() / ".config" / "usage-statusline" / "omniroute.json"
CACHE = Path.home() / ".cache" / "usage-statusline" / "omniroute.json"
URL = "http://127.0.0.1:20128/api/usage/om-usage?format=json"
CACHE_TTL = 60
TIMEOUT = 2

CONFIG_ERROR = "configuration error; check omniroute.json"
UNAVAILABLE = "selected connection unavailable"
QUOTA_ERROR = "quota unavailable or inconsistent"
FETCH_FAILED = "fetch failed"
PROVIDERS = {"claude": "Claude", "codex": "Codex", "agy": "AG"}
TOLERANCE = 1e-8
MAX_BODY = 4 * 1024 * 1024


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(QUOTA_ERROR)
    return value


def _percent(value: object) -> float:
    number = _number(value)
    if not 0 <= number <= 100:
        raise ValueError(QUOTA_ERROR)
    return number


def _reset(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError(QUOTA_ERROR)
    when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError(QUOTA_ERROR)
    return when


def _meter(meter: object) -> dict:
    if not isinstance(meter, dict) or meter.get("unlimited", False) is not False:
        raise ValueError(QUOTA_ERROR)
    return meter


def _used_window(meter: object) -> tuple[float, datetime]:
    """Claude/Codex meter: used/total100 percent, optional consistent remainingPercentage."""
    meter = _meter(meter)
    used = _percent(meter.get("used"))
    if _number(meter.get("total")) != 100:
        raise ValueError(QUOTA_ERROR)
    if "remainingPercentage" in meter:
        if abs(_percent(meter["remainingPercentage"]) - (100 - used)) > 0.1:
            raise ValueError(QUOTA_ERROR)
    return used, _reset(meter.get("resetAt"))


def _ag_window(meter: object) -> tuple[float, datetime]:
    """AG meter: used/total is rounded, so remainingPercentage is authoritative."""
    meter = _meter(meter)
    return 100 - _percent(meter.get("remainingPercentage")), _reset(meter.get("resetAt"))


def _collapse(windows: list[tuple[float, datetime]]) -> tuple[float, datetime]:
    """One value only if every candidate agrees; never pick an arbitrary one."""
    if not windows:
        raise ValueError(QUOTA_ERROR)
    first = windows[0]
    if any(abs(w[0] - first[0]) > TOLERANCE or w[1] != first[1] for w in windows):
        raise ValueError(QUOTA_ERROR)
    return first


def _claude_rows(quotas: dict, tag: str) -> list[str]:
    session, week = (_used_window(quotas.get(key)) for key in ("session (5h)", "weekly (7d)"))
    return [fmt_line("Claude" + tag, fmt_windows(session, week))]


def _codex_rows(quotas: dict, tag: str) -> list[str]:
    columns: list[tuple[float, datetime] | None] = [None, None]
    second_label = "week"
    found = False
    for key in ("session", "weekly"):
        if key not in quotas:
            continue
        found = True
        window = _used_window(quotas[key])
        seconds = quotas[key].get("windowSeconds")
        if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds <= 0:
            raise ValueError(QUOTA_ERROR)
        column = 0 if seconds <= 86400 else 1
        if columns[column] is not None:
            raise ValueError(QUOTA_ERROR)
        columns[column] = window
        if column == 1 and seconds != 604800:
            if seconds % 86400:
                raise ValueError(QUOTA_ERROR)
            second_label = f"{seconds // 86400}d"
    if not found:
        raise ValueError(QUOTA_ERROR)
    body = fmt_windows(columns[0], columns[1], ("session", second_label))
    return [fmt_line("Codex" + tag, body)]


def _ag_rows(quotas: dict, tag: str, label: str | None = None) -> list[str]:
    rows = []
    for name, key, prefixes in (
        ("AG Gemini", "gemini_weekly", ("gemini-",)),
        ("AG Claude/GPT", "claude_gpt_weekly", ("claude-", "gpt-")),
        ("AG Argon", "gemini_4_argon_weekly", ()),
    ):
        if label is not None and name != label:
            continue
        candidates = [
            _ag_window(m)
            for k, m in quotas.items()
            if k.startswith(prefixes) and not k.startswith("gemini-4-argon-")
        ]
        session = _collapse(candidates) if candidates else None
        week = _ag_window(quotas[key]) if key in quotas else None
        if session is None and week is None:
            raise ValueError(QUOTA_ERROR)
        rows.append(fmt_line(name + tag, fmt_windows(session, week)))
    return rows


def parse_connection(snapshot: dict, selection: dict, ag_label: str | None = None) -> list[str]:
    """Validated rows for the selected connection; ValueError carries only a static message."""
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("connectionId") != selection["connection_id"]
        or snapshot.get("provider") != selection["provider"]
    ):
        raise ValueError(UNAVAILABLE)
    tag = f" [{selection['alias']}]" if selection.get("alias") else ""
    try:
        quotas = snapshot.get("quotas")
        if not isinstance(quotas, dict):
            raise ValueError(QUOTA_ERROR)
        if selection["provider"] == "agy":
            return _ag_rows(quotas, tag, ag_label)
        build = {"claude": _claude_rows, "codex": _codex_rows}
        return build[selection["provider"]](quotas, tag)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(QUOTA_ERROR) from None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch_snapshot(key: str) -> dict:
    """One authenticated GET with environment proxies and redirects disabled."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    request = urllib.request.Request(URL, method="GET")
    request.add_unredirected_header("Authorization", f"Bearer {key}")
    with opener.open(request, timeout=TIMEOUT) as response:
        data = json.loads(response.read(MAX_BODY))
    if (
        not isinstance(data, dict)
        or data.get("allowed") is not True
        or not isinstance(data.get("providers"), list)
    ):
        raise ValueError(FETCH_FAILED)
    return data


def _fetch_error(error: Exception) -> str:
    if isinstance(error, urllib.error.HTTPError):
        if error.code == 401:
            return "HTTP 401; check usage key"
        if error.code == 403:
            return "HTTP 403; enable usage permission"
        if 300 <= error.code < 400:
            return "redirect rejected"
    return FETCH_FAILED


def _printable(text: object) -> bool:
    return isinstance(text, str) and text.isprintable()


def _load_config(text: str) -> tuple[dict, list[dict]]:
    data = json.loads(text)
    if not isinstance(data, dict) or set(data) != {"key_file", "connections"}:
        raise ValueError
    key_file, connections = data["key_file"], data["connections"]
    if not _printable(key_file) or not key_file or not Path(key_file).expanduser().is_absolute():
        raise ValueError
    if not isinstance(connections, list) or not connections:
        raise ValueError
    seen = set()
    for item in connections:
        if not isinstance(item, dict) or not {"provider", "connection_id"} <= set(item):
            raise ValueError
        if set(item) - {"provider", "connection_id", "alias"}:
            raise ValueError
        ident = item["connection_id"]
        if item["provider"] not in PROVIDERS or not _printable(ident) or not ident:
            raise ValueError
        if ident in seen:
            raise ValueError
        seen.add(ident)
        if "alias" in item:
            alias = item["alias"]
            if not _printable(alias) or not 1 <= len(alias) <= 32 or alias != alias.strip():
                raise ValueError
    return data, connections


def _read_key(key_file: str) -> str:
    key = Path(key_file).expanduser().read_text().strip()
    if not key or not key.isprintable():
        raise ValueError
    return key


def _timestamp(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int | float) and math.isfinite(value)


def _read_cache(cache: Path, scope: str, ids: set[str], now: float) -> tuple[float, str, dict]:
    """(attempted_at, line, valid records); raises on a missing or invalid cache."""
    stored = json.loads(cache.read_text())
    version = stored["version"]
    if (
        type(version) is not int
        or version != 1
        or stored["scope"] != scope
        or not _timestamp(stored["attempted_at"])
    ):
        raise ValueError
    line, connections = stored["line"], stored["connections"]
    if not isinstance(line, str) or not isinstance(connections, dict):
        raise ValueError
    records = {}
    for ident, record in connections.items():
        try:
            rows, received = record["rows"], record["received_at"]
            if (
                ident in ids
                and isinstance(rows, list)
                and rows
                and all(_printable(r) for r in rows)
                and _timestamp(received)
                and received <= now
                and datetime.fromtimestamp(received)
            ):
                row_times = record.get("row_times", [received] * len(rows))
                if not isinstance(row_times, list) or len(row_times) != len(rows):
                    continue
                if not all(
                    _timestamp(t) and t <= now and datetime.fromtimestamp(t) for t in row_times
                ):
                    continue
                records[ident] = {"rows": rows, "received_at": received, "row_times": row_times}
        except (TypeError, KeyError, OverflowError, OSError, ValueError):
            continue
    return stored["attempted_at"], line, records


def _stale(record: dict) -> list[str]:
    rows = []
    times = record.get("row_times", [record["received_at"]] * len(record["rows"]))
    for row, received in zip(record["rows"], times, strict=True):
        marker = datetime.fromtimestamp(received).strftime("%Y-%m-%d %H:%M")
        rows.append(f"{row} · stale (received {marker})")
    return rows


def _write_cache(cache: Path, payload: dict) -> None:
    temporary = None
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=cache.parent, delete=False) as file:
            temporary = Path(file.name)
            os.chmod(file.name, 0o600)
            json.dump(payload, file)
        os.replace(temporary, cache)
    except OSError:
        pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _error_line(message: str, label: str = "OmniRoute") -> str:
    return fmt_line(label, f"n/a ({message})")


def omniroute_lines(
    config: Path = CONFIG, cache: Path = CACHE, now: float | None = None
) -> str | None:
    """Router-sourced lines; None only when no config exists."""
    header = fmt_line("OmniRoute", "upstream age unknown")
    try:
        text = config.read_text()
    except FileNotFoundError:
        if not config.is_symlink():
            return None
        return header + "\n" + _error_line(CONFIG_ERROR)
    except (OSError, ValueError):
        return header + "\n" + _error_line(CONFIG_ERROR)
    try:
        data, selections = _load_config(text)
    except (ValueError, TypeError, RuntimeError):
        return header + "\n" + _error_line(CONFIG_ERROR)

    now = time.time() if now is None else now
    scope = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    ids = {s["connection_id"] for s in selections}
    records: dict = {}
    try:
        attempted, line, prior = _read_cache(cache, scope, ids, now)
        if now - attempted >= 0:
            if now - attempted < CACHE_TTL:
                parts = line.splitlines()
                allowed = {
                    _error_line(m)
                    for m in (
                        CONFIG_ERROR,
                        FETCH_FAILED,
                        "HTTP 401; check usage key",
                        "HTTP 403; enable usage permission",
                        "redirect rejected",
                    )
                }
                for selection in selections:
                    tag = f" [{selection['alias']}]" if selection.get("alias") else ""
                    for message in (UNAVAILABLE, QUOTA_ERROR):
                        allowed.add(_error_line(message, PROVIDERS[selection["provider"]] + tag))
                    if selection["provider"] == "agy":
                        for label in ("AG Gemini", "AG Claude/GPT", "AG Argon"):
                            allowed.add(_error_line(QUOTA_ERROR, label + tag))
                    record = prior.get(selection["connection_id"])
                    if record:
                        allowed.update(record["rows"])
                        allowed.update(_stale(record))
                if parts[:1] == [header] and all(p in allowed for p in parts[1:]):
                    return line
            records = prior
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError):
        records = {}

    lines = [header]
    connections = dict(records)
    snapshot = None
    try:
        key = _read_key(data["key_file"])
    except (OSError, ValueError, RuntimeError):
        lines.append(_error_line(CONFIG_ERROR))
    else:
        try:
            snapshot = fetch_snapshot(key)
        except Exception as error:  # Sanitized to a static message.
            lines.append(_error_line(_fetch_error(error)))
    for selection in selections:
        ident = selection["connection_id"]
        record = records.get(ident)
        if snapshot is None:
            lines.extend(_stale(record) if record else [])
            continue
        matches = [
            p
            for p in snapshot["providers"]
            if isinstance(p, dict) and p.get("connectionId") == ident
        ]
        try:
            if len(matches) != 1:
                raise ValueError(UNAVAILABLE)
            if selection["provider"] == "agy":
                tag = f" [{selection['alias']}]" if selection.get("alias") else ""
                rows, row_times, rendered = [], [], []
                fresh = False
                for label in ("AG Gemini", "AG Claude/GPT", "AG Argon"):
                    try:
                        row = parse_connection(matches[0], selection, label)[0]
                    except ValueError:
                        prefix = fmt_line(label + tag, "")
                        previous = (
                            next(
                                (i for i, r in enumerate(record["rows"]) if r.startswith(prefix)),
                                None,
                            )
                            if record
                            else None
                        )
                        if record is None or previous is None:
                            rendered.append(_error_line(QUOTA_ERROR, label + tag))
                            continue
                        row = record["rows"][previous]
                        received = record.get(
                            "row_times", [record["received_at"]] * len(record["rows"])
                        )[previous]
                        rendered.extend(_stale({"rows": [row], "received_at": received}))
                    else:
                        fresh = True
                        received = now
                        rendered.append(row)
                    rows.append(row)
                    row_times.append(received)
                if not fresh:
                    parse_connection(matches[0], selection)
                lines.extend(rendered)
                connections[ident] = {"rows": rows, "received_at": now, "row_times": row_times}
                continue
            rows = parse_connection(matches[0], selection)
        except ValueError as error:
            message = str(error) if str(error) == UNAVAILABLE else QUOTA_ERROR
            lines.extend(_stale(record) if record else [])
            tag = f" [{selection['alias']}]" if selection.get("alias") else ""
            lines.append(_error_line(message, PROVIDERS[selection["provider"]] + tag))
        else:
            lines.extend(rows)
            connections[ident] = {"rows": rows, "received_at": now}
    output = "\n".join(lines)
    _write_cache(
        cache,
        {
            "version": 1,
            "scope": scope,
            "attempted_at": now,
            "line": output,
            "connections": connections,
        },
    )
    return output
