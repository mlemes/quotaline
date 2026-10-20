import copy
import io
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import Mock

import pytest

from usage_statusline import omniroute as o
from usage_statusline.claude import fmt_line, fmt_windows

HEADER = fmt_line("OmniRoute", "upstream age unknown")
CONFIG_ERROR = fmt_line("OmniRoute", "n/a (configuration error; check omniroute.json)")
SECRET = "sentinel-private-usage-key"
NOW = 1_800_000_000.0


@pytest.fixture
def snapshot():
    return json.loads((Path(__file__).parent / "fixtures/omniroute.json").read_text())


@pytest.fixture
def setup(tmp_path, monkeypatch, snapshot):
    key = tmp_path / "private-key"
    key.write_text(SECRET + "\n")
    config = tmp_path / "config.json"
    data = {
        "key_file": str(key),
        "connections": [
            {"provider": p, "connection_id": f"test-{p}-connection"}
            for p in ("claude", "agy", "codex")
        ],
    }
    config.write_text(json.dumps(data))
    cache = tmp_path / "cache.json"
    fetch = Mock(return_value=snapshot)
    monkeypatch.setattr(o, "fetch_snapshot", fetch)
    return config, cache, data, key, fetch


def selected(snapshot, provider):
    item = next(p for p in snapshot["providers"] if p["provider"] == provider)
    return item, {"provider": provider, "connection_id": item["connectionId"]}


QUOTA_NA = "n/a (quota unavailable or inconsistent)"
GEMINI_ERROR = fmt_line("AG Gemini", QUOTA_NA)


def row(label, first, second, labels=("session", "week")):
    def window(value):
        return None if value is None else (value[0], datetime.fromisoformat(value[1]))

    return fmt_line(label, fmt_windows(window(first), window(second), labels))


FRESH = {
    "AG Gemini": row(
        "AG Gemini", (18.02083, "2026-10-19T05:15:15Z"), (6.20262, "2026-10-24T02:56:06Z")
    ),
    "AG Claude/GPT": row(
        "AG Claude/GPT", (0.0012, "2026-10-19T07:26:06Z"), (0.33808, "2026-10-21T15:34:26Z")
    ),
    "AG Argon": row("AG Argon", None, (100, "2026-10-25T00:34:41Z")),
}


def ag_lines(output):
    """Map AG label (text before the first two-space gap) to full line."""
    return {
        line.split("  ")[0].strip(): line
        for line in output.splitlines()
        if line.startswith(("AG", "Antigravity"))
    }


def test_fixture_preserves_percentages_resets_and_argon_separation(snapshot):
    expected = {
        "claude": [
            row("Claude", (1, "2026-10-19T06:30:00.155Z"), (98, "2026-10-19T14:00:00.156Z"))
        ],
        "codex": [row("Codex", (78, "2026-10-19T06:22:53Z"), (16, "2026-10-24T21:13:11Z"))],
        "agy": [
            row("AG Gemini", (18.02083, "2026-10-19T05:15:15Z"), (6.20262, "2026-10-24T02:56:06Z")),
            row(
                "AG Claude/GPT", (0.0012, "2026-10-19T07:26:06Z"), (0.33808, "2026-10-21T15:34:26Z")
            ),
            row("AG Argon", None, (100, "2026-10-25T00:34:41Z")),
        ],
    }
    for provider, rows in expected.items():
        item, selection = selected(snapshot, provider)
        assert o.parse_connection(item, selection) == rows
    ag, selection = selected(snapshot, "agy")
    for meter in ag["quotas"].values():
        meter["used"] = 999
    assert o.parse_connection(ag, selection) == expected["agy"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("used", None),
        ("used", "1"),
        ("used", True),
        ("used", -1),
        ("used", 101),
        ("used", float("nan")),
        ("used", float("inf")),
        ("total", 1),
        ("total", True),
        ("total", None),
        ("remainingPercentage", "99"),
        ("remainingPercentage", False),
        ("remainingPercentage", 95),
        ("remainingPercentage", float("nan")),
        ("unlimited", True),
        ("resetAt", None),
        ("resetAt", "bad"),
        ("resetAt", "2026-10-19T06:30:00"),
        ("resetAt", 1),
    ],
)
def test_claude_rejects_invalid_quota(snapshot, field, value):
    item, selection = selected(snapshot, "claude")
    item["quotas"]["session (5h)"][field] = value
    with pytest.raises(ValueError):
        o.parse_connection(item, selection)


@pytest.mark.parametrize(
    "provider,key",
    [
        ("claude", "session (5h)"),
        ("claude", "weekly (7d)"),
    ],
)
def test_missing_required_meter_is_invalid(snapshot, provider, key):
    item, selection = selected(snapshot, provider)
    del item["quotas"][key]
    with pytest.raises(ValueError):
        o.parse_connection(item, selection)


@pytest.mark.parametrize("value", [None, True, "80", -1, 101, float("nan"), float("inf")])
def test_ag_requires_valid_authoritative_remaining(setup, snapshot, value):
    config, cache, _, _, _ = setup
    item, _ = selected(snapshot, "agy")
    item["quotas"]["gemini_weekly"]["remainingPercentage"] = value
    lines = ag_lines(o.omniroute_lines(config, cache, now=NOW))
    assert lines["AG Gemini"] == GEMINI_ERROR
    assert (
        lines["AG Claude/GPT"] == FRESH["AG Claude/GPT"] and lines["AG Argon"] == FRESH["AG Argon"]
    )


@pytest.mark.parametrize("change", ["percent", "reset"])
def test_ag_never_arbitrarily_picks_family_candidate(setup, snapshot, change):
    config, cache, _, _, _ = setup
    item, _ = selected(snapshot, "agy")
    quotas = item["quotas"]
    if change == "percent":
        quotas["gemini-3.8-flash-high"]["remainingPercentage"] -= 1
        failed, ok = "AG Gemini", "AG Claude/GPT"
    else:
        quotas["gpt-oss-120b-medium"]["resetAt"] = "2026-10-20T00:00:00Z"
        failed, ok = "AG Claude/GPT", "AG Gemini"
    lines = ag_lines(o.omniroute_lines(config, cache, now=NOW))
    assert lines[failed] == fmt_line(failed, QUOTA_NA)
    assert lines[ok] == FRESH[ok] and lines["AG Argon"] == FRESH["AG Argon"]


def test_ag_equivalent_aware_resets_and_unknown_keys_are_accepted(snapshot):
    item, selection = selected(snapshot, "agy")
    before = o.parse_connection(item, selection)
    item["quotas"]["gemini-3.8-flash-high"]["resetAt"] = "2026-10-19T02:15:15-03:00"
    item["quotas"]["chat_internal"] = {"used": "do not inspect"}
    assert o.parse_connection(item, selection) == before


def test_past_resets_do_not_zero_usage(snapshot):
    item, selection = selected(snapshot, "claude")
    item["quotas"]["session (5h)"]["resetAt"] = "2000-01-01T00:00:00Z"
    assert "session   1%" in o.parse_connection(item, selection)[0]


def test_codex_long_session_is_second_column_with_30d_label(snapshot):
    item, selection = selected(snapshot, "codex")
    meter = item["quotas"]["session"]
    meter["windowSeconds"] = 2_592_000
    item["quotas"] = {"session": meter}
    assert o.parse_connection(item, selection) == [
        row("Codex", None, (78, meter["resetAt"]), ("session", "30d"))
    ]


@pytest.mark.parametrize("duration", [None, True, 0, -1, 1.5, "18000", float("inf"), 86401])
def test_codex_rejects_invalid_or_unrepresentable_duration(snapshot, duration):
    item, selection = selected(snapshot, "codex")
    item["quotas"]["session"]["windowSeconds"] = duration
    with pytest.raises(ValueError):
        o.parse_connection(item, selection)


def test_codex_rejects_fraction_schema_and_conflicting_columns(snapshot):
    item, selection = selected(snapshot, "codex")
    for meter in item["quotas"].values():
        meter["total"] = 1
        meter["used"] = 0.5
    with pytest.raises(ValueError):
        o.parse_connection(item, selection)
    item, selection = selected(
        copy.deepcopy(json.loads((Path(__file__).parent / "fixtures/omniroute.json").read_text())),
        "codex",
    )
    item["quotas"]["weekly"]["windowSeconds"] = 18000
    with pytest.raises(ValueError):
        o.parse_connection(item, selection)


@pytest.mark.parametrize(
    "field,value", [("connectionId", "private-wrong-id"), ("provider", "private-provider")]
)
def test_parse_connection_validates_identity_without_echo(snapshot, field, value):
    item, selection = selected(snapshot, "claude")
    item[field] = value
    with pytest.raises(ValueError) as error:
        o.parse_connection(item, selection)
    assert value not in str(error.value)


def test_absent_config_is_only_none_case(tmp_path):
    assert o.omniroute_lines(tmp_path / "absent", tmp_path / "cache", now=NOW) is None


@pytest.mark.parametrize(
    "invalid",
    [
        [],
        {},
        {"key_file": "relative", "connections": []},
        {"key_file": "/tmp/x", "connections": "wrong"},
    ],
)
def test_invalid_top_level_config(setup, invalid):
    config, cache, _, _, fetch = setup
    config.write_text(json.dumps(invalid))
    assert o.omniroute_lines(config, cache, now=NOW) == HEADER + "\n" + CONFIG_ERROR
    fetch.assert_not_called()


@pytest.mark.parametrize(
    "mutation",
    [
        "extra_top",
        "extra_selection",
        "provider",
        "empty",
        "duplicate",
        "alias_newline",
        "alias_escape",
        "alias_long",
        "alias_empty",
        "alias_space",
        "id_control",
        "relative_key",
    ],
)
def test_invalid_mapping_is_static_configuration_error(setup, mutation):
    config, cache, data, _, fetch = setup
    selection = data["connections"][0]
    if mutation == "extra_top":
        data["discover"] = True
    elif mutation == "extra_selection":
        selection["extra"] = True
    elif mutation == "provider":
        selection["provider"] = "private-unsupported-provider"
    elif mutation == "empty":
        data["connections"] = []
    elif mutation == "duplicate":
        data["connections"].append(dict(selection))
    elif mutation == "id_control":
        selection["connection_id"] = "private\nidentifier"
    elif mutation == "relative_key":
        data["key_file"] = "relative/private-key"
    else:
        selection["alias"] = {
            "alias_newline": "bad\nvalue",
            "alias_escape": "bad\x1b",
            "alias_long": "x" * 33,
            "alias_empty": "",
            "alias_space": " x",
        }[mutation]
    config.write_text(json.dumps(data))
    assert o.omniroute_lines(config, cache, now=NOW) == HEADER + "\n" + CONFIG_ERROR
    fetch.assert_not_called()


@pytest.mark.parametrize("kind", ["json", "dangling", "unreadable"])
def test_broken_existing_config_never_becomes_absent(setup, monkeypatch, kind):
    config, cache, _, _, fetch = setup
    if kind == "json":
        config.write_text("{private-broken-json")
    elif kind == "dangling":
        config.unlink()
        config.symlink_to(config.parent / "missing-target")
    else:
        original = Path.read_text

        def unreadable(path, *args, **kwargs):
            if path == config:
                raise PermissionError("private-path")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", unreadable)
    assert o.omniroute_lines(config, cache, now=NOW) == HEADER + "\n" + CONFIG_ERROR
    fetch.assert_not_called()


@pytest.mark.parametrize("key_text", ["", "  \n", "two\nlines", "key\x1b", "key\x00"])
def test_bad_key_is_sanitized_without_fetch(setup, key_text, capsys):
    config, cache, _, key, fetch = setup
    key.write_text(key_text)
    output = o.omniroute_lines(config, cache, now=NOW)
    assert "n/a" in output and output.startswith(HEADER)
    assert "two" not in output and str(key) not in output
    fetch.assert_not_called()
    assert capsys.readouterr() == ("", "")


def test_config_order_aliases_exact_account_and_no_secret_in_cache(setup, snapshot, capsys):
    config, cache, data, _, fetch = setup
    data["connections"][0]["alias"] = "work"
    other = copy.deepcopy(snapshot["providers"][1])
    other["connectionId"] = "second-claude"
    other["quotas"]["session (5h)"]["used"] = 7
    other["quotas"]["session (5h)"]["remainingPercentage"] = 93
    snapshot["providers"].insert(0, other)
    data["connections"].append({"provider": "claude", "connection_id": "second-claude"})
    config.write_text(json.dumps(data))
    output = o.omniroute_lines(config, cache, now=NOW)
    lines = output.splitlines()
    assert lines[0] == HEADER and output.count(HEADER) == 1
    assert lines[1].startswith("Claude [work]") and "session   1%" in lines[1]
    assert [line.split("session")[0].strip() for line in lines[2:5]] == [
        "AG Gemini",
        "AG Claude/GPT",
        "AG Argon",
    ]
    assert lines[5].startswith("Codex")
    assert lines[6].startswith("Claude") and "session   7%" in lines[6]
    fetch.assert_called_once_with(SECRET)
    stored = cache.read_text()
    for private in (
        SECRET,
        str(config.parent / "private-key"),
        "unselected-router-preference",
        "remainingPercentage",
        "personal",
        "resetAt",
    ):
        assert private not in output + stored
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("failure", ["missing", "duplicate", "mismatch", "quota"])
def test_selected_account_failure_is_isolated(setup, snapshot, failure):
    config, cache, _, _, _ = setup
    item, _ = selected(snapshot, "claude")
    if failure == "missing":
        snapshot["providers"].remove(item)
    elif failure == "duplicate":
        snapshot["providers"].append(copy.deepcopy(item))
    elif failure == "mismatch":
        item["provider"] = "codex"
    else:
        del item["quotas"]["weekly (7d)"]
    output = o.omniroute_lines(config, cache, now=NOW)
    error = (
        "quota unavailable or inconsistent"
        if failure == "quota"
        else ("selected connection unavailable")
    )
    assert fmt_line("Claude", f"n/a ({error})") in output
    assert "session  78%" in output and "AG Argon" in output
    assert "test-claude-connection" not in output


def test_transport_request_is_fixed_authenticated_private_and_proxy_free(monkeypatch, snapshot):
    seen = {}

    class Opener:
        def open(self, request, timeout):
            seen.update(request=request, timeout=timeout)
            return io.BytesIO(json.dumps(snapshot).encode())

    def build(*handlers):
        seen["handlers"] = handlers
        return Opener()

    monkeypatch.setenv("HTTP_PROXY", "http://private-proxy.invalid")
    monkeypatch.setattr(urllib.request, "build_opener", build)
    assert o.fetch_snapshot(SECRET) == snapshot
    assert o.URL == "http://127.0.0.1:20128/api/usage/om-usage?format=json"
    request = seen["request"]
    assert request.full_url == o.URL and request.get_method() == "GET"
    assert seen["timeout"] == 2
    assert request.unredirected_hdrs.get("Authorization") == "Bearer " + SECRET
    assert "Authorization" not in request.headers
    proxies = [h for h in seen["handlers"] if isinstance(h, urllib.request.ProxyHandler)]
    assert proxies and proxies[0].proxies == {}


def test_transport_rejects_redirect_without_followup_or_auth_leak(monkeypatch):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.path, self.headers.get("Authorization")))
            self.send_response(302)
            self.send_header("Location", "/must-not-follow")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(o, "URL", f"http://127.0.0.1:{server.server_port}/usage")
    try:
        with pytest.raises((ValueError, urllib.error.HTTPError)):
            o.fetch_snapshot(SECRET)
        assert seen == [("/usage", "Bearer " + SECRET)]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    "payload",
    [
        b"broken-private-json",
        b"[]",
        b"null",
        b"{}",
        b'{"allowed":1,"providers":[]}',
        b'{"allowed":false,"providers":[]}',
        b'{"allowed":true,"providers":{}}',
    ],
)
def test_transport_rejects_invalid_protocol(monkeypatch, payload):
    opener = Mock()
    opener.open.return_value = io.BytesIO(payload)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: opener)
    with pytest.raises((ValueError, TypeError)):
        o.fetch_snapshot(SECRET)


@pytest.mark.parametrize(
    "error,message",
    [
        (
            urllib.error.HTTPError("private-url", 401, SECRET, None, None),
            "HTTP 401; check usage key",
        ),
        (
            urllib.error.HTTPError("private-url", 403, SECRET, None, None),
            "HTTP 403; enable usage permission",
        ),
        (urllib.error.HTTPError("private-url", 302, SECRET, None, None), "redirect rejected"),
        (TimeoutError(SECRET), "fetch failed"),
        (ValueError(SECRET), "fetch failed"),
        (urllib.error.URLError(SECRET), "fetch failed"),
    ],
)
def test_global_errors_are_static_and_cached(setup, error, message, capsys):
    config, cache, _, _, fetch = setup
    fetch.side_effect = error
    output = o.omniroute_lines(config, cache, now=NOW)
    assert output == HEADER + "\n" + fmt_line("OmniRoute", f"n/a ({message})")
    assert o.omniroute_lines(config, cache, now=NOW + 59.9) == output
    assert fetch.call_count == 1
    assert SECRET not in output + cache.read_text()
    assert capsys.readouterr() == ("", "")


def test_cache_ttl_skips_key_read_and_refreshes_at_exact_boundary(setup):
    config, cache, _, key, fetch = setup
    output = o.omniroute_lines(config, cache, now=NOW)
    key.unlink()
    assert o.omniroute_lines(config, cache, now=NOW + 59.9) == output
    assert fetch.call_count == 1
    key.write_text(SECRET)
    assert o.omniroute_lines(config, cache, now=NOW + 60) == output
    assert fetch.call_count == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("attempted_at", True),
        ("attempted_at", float("nan")),
        ("attempted_at", float("inf")),
        ("attempted_at", NOW + 1),
        ("version", 2),
        ("version", True),
        ("scope", "wrong"),
        ("line", ["wrong"]),
    ],
)
def test_invalid_cache_is_miss(setup, field, value):
    config, cache, _, _, fetch = setup
    o.omniroute_lines(config, cache, now=NOW)
    stored = json.loads(cache.read_text())
    stored[field] = value
    cache.write_text(json.dumps(stored))
    o.omniroute_lines(config, cache, now=NOW)
    assert fetch.call_count == 2


def test_corrupt_cache_is_miss(setup):
    config, cache, _, _, fetch = setup
    cache.write_text("not json")
    assert "session  78%" in o.omniroute_lines(config, cache, now=NOW)
    fetch.assert_called_once()


@pytest.mark.parametrize("mutation", ["alias", "order", "id", "key_path"])
def test_config_scope_change_never_resurrects_previous_rows(setup, mutation):
    config, cache, data, key, fetch = setup
    o.omniroute_lines(config, cache, now=NOW)
    if mutation == "alias":
        data["connections"][0]["alias"] = "new"
    elif mutation == "order":
        data["connections"].reverse()
    elif mutation == "id":
        data["connections"][0]["connection_id"] = "new-id"
    else:
        new_key = key.with_name("other-key")
        new_key.write_text(SECRET)
        data["key_file"] = str(new_key)
    config.write_text(json.dumps(data))
    fetch.side_effect = TimeoutError(SECRET)
    output = o.omniroute_lines(config, cache, now=NOW + 1)
    assert fetch.call_count == 2
    assert output == HEADER + "\n" + fmt_line("OmniRoute", "n/a (fetch failed)")


def test_partial_response_keeps_only_failed_connection_at_original_receipt(setup, snapshot):
    config, cache, _, _, fetch = setup
    initial = o.omniroute_lines(config, cache, now=NOW)
    item, _ = selected(snapshot, "claude")
    snapshot["providers"].remove(item)
    codex, _ = selected(snapshot, "codex")
    codex["quotas"]["session"]["used"] = 42
    partial = o.omniroute_lines(config, cache, now=NOW + 60)
    marker = datetime.fromtimestamp(NOW).strftime("%Y-%m-%d %H:%M")
    assert initial.splitlines()[1] + f" · stale (received {marker})" in partial
    assert "selected connection unavailable" in partial
    assert "session  42%" in partial and "session  78%" not in partial
    assert partial.count(" · stale (received ") == 1
    fetch.side_effect = TimeoutError(SECRET)
    failed = o.omniroute_lines(config, cache, now=NOW + 120)
    repeated = o.omniroute_lines(config, cache, now=NOW + 180)
    assert failed == repeated
    assert f"received {marker}" in failed and failed.count(" · stale (received ") == 5
    assert "stale" not in json.dumps(json.loads(cache.read_text()).get("connections", {}))


@pytest.mark.parametrize("bad", ["rows", "received_at"])
def test_corrupt_success_record_cannot_spoof_stale_multiline(setup, bad):
    config, cache, _, _, fetch = setup
    o.omniroute_lines(config, cache, now=NOW)
    stored = json.loads(cache.read_text())
    records = [
        value
        for value in stored.values()
        if isinstance(value, dict) and "test-claude-connection" in value
    ]
    assert len(records) == 1
    record = records[0]["test-claude-connection"]
    record[bad] = ["safe\nSPOOFED"] if bad == "rows" else NOW + 1000
    cache.write_text(json.dumps(stored))
    fetch.side_effect = TimeoutError(SECRET)
    output = o.omniroute_lines(config, cache, now=NOW + 60)
    assert "SPOOFED" not in output
    assert "Claude         session" not in output
    assert "fetch failed" in output


def test_cache_replacement_is_private_atomic_and_leaves_no_temp(setup, monkeypatch):
    config, cache, _, _, _ = setup
    cache.write_text("old")
    cache.chmod(0o666)
    original = os.replace
    replaced = []

    def replace(source, destination):
        assert Path(source).parent == cache.parent
        assert Path(source).stat().st_mode & 0o777 == 0o600
        assert Path(destination) == cache
        assert cache.read_text() == "old"
        replaced.append(True)
        return original(source, destination)

    monkeypatch.setattr(os, "replace", replace)
    before = set(cache.parent.iterdir())
    assert "session  78%" in o.omniroute_lines(config, cache, now=NOW)
    assert replaced and cache.stat().st_mode & 0o777 == 0o600
    assert set(cache.parent.iterdir()) == before


@pytest.mark.parametrize("failure", ["mkdir", "replace"])
def test_cache_write_failure_does_not_hide_fresh_output_or_leave_temp(setup, monkeypatch, failure):
    config, cache, _, _, _ = setup
    before = set(cache.parent.iterdir())
    if failure == "mkdir":

        def fail(*args, **kwargs):
            raise PermissionError("private-cache-path")

        monkeypatch.setattr(Path, "mkdir", fail)
        cache = cache / "unwritable" / "cache.json"
    else:

        def fail(*args, **kwargs):
            raise PermissionError("private-cache-path")

        monkeypatch.setattr(os, "replace", fail)
    assert "session  78%" in o.omniroute_lines(config, cache, now=NOW)
    assert set(config.parent.iterdir()) == before


@pytest.mark.parametrize("suffix", ["\x1bUNTRUSTED", "\x00UNTRUSTED", "\nUNTRUSTED forged row"])
def test_valid_ttl_rejects_control_or_forged_cached_line(setup, suffix):
    config, cache, _, _, fetch = setup
    clean = o.omniroute_lines(config, cache, now=NOW)
    stored = json.loads(cache.read_text())
    stored["line"] += suffix
    cache.write_text(json.dumps(stored))
    assert o.omniroute_lines(config, cache, now=NOW + 1) == clean
    assert fetch.call_count == 2


@pytest.mark.parametrize(
    "corruption",
    [
        "bool_time",
        "nan_time",
        "inf_time",
        "scalar_record",
        "scalar_rows",
        "control_row",
    ],
)
def test_corrupt_success_records_are_never_reused_after_failure(setup, corruption):
    config, cache, _, _, fetch = setup
    o.omniroute_lines(config, cache, now=NOW)
    stored = json.loads(cache.read_text())
    records = next(
        value
        for value in stored.values()
        if isinstance(value, dict) and "test-claude-connection" in value
    )
    record = records["test-claude-connection"]
    if corruption == "scalar_record":
        records["test-claude-connection"] = "UNTRUSTED"
    elif corruption == "scalar_rows":
        record["rows"] = "UNTRUSTED"
    elif corruption == "control_row":
        record["rows"] = ["Claude         session   1%\x1bUNTRUSTED"]
    else:
        record["received_at"] = {
            "bool_time": True,
            "nan_time": float("nan"),
            "inf_time": float("inf"),
        }[corruption]
    cache.write_text(json.dumps(stored))
    fetch.side_effect = TimeoutError(SECRET)
    output = o.omniroute_lines(config, cache, now=NOW + 60)
    assert "UNTRUSTED" not in output and "session   1%" not in output
    assert "fetch failed" in output


@pytest.mark.parametrize(
    "mutation",
    [
        "null_meter",
        "scalar_meter",
        "unlimited",
        "null_reset",
        "naive_reset",
        "missing_remaining",
    ],
)
def test_every_ag_family_candidate_must_be_valid(snapshot, mutation):
    item, selection = selected(snapshot, "agy")
    key = "gemini-3.8-flash-high"
    meter = item["quotas"][key]
    if mutation in ("null_meter", "scalar_meter"):
        item["quotas"][key] = None if mutation == "null_meter" else "UNTRUSTED"
    elif mutation == "unlimited":
        meter["unlimited"] = True
    elif mutation == "null_reset":
        meter["resetAt"] = None
    elif mutation == "naive_reset":
        meter["resetAt"] = "2026-10-19T05:15:15"
    else:
        del meter["remainingPercentage"]
    with pytest.raises(ValueError):
        o.parse_connection(item, selection)


@pytest.mark.parametrize("quotas", [None, "UNTRUSTED", [], 7])
def test_malformed_selected_quotas_leave_healthy_accounts_visible(setup, snapshot, quotas):
    config, cache, _, _, _ = setup
    item, _ = selected(snapshot, "claude")
    item["quotas"] = quotas
    snapshot["providers"][:0] = [None, "UNTRUSTED", 42, [], {"quotas": "UNTRUSTED"}]
    output = o.omniroute_lines(config, cache, now=NOW)
    assert fmt_line("Claude", "n/a (quota unavailable or inconsistent)") in output
    assert "session  78%" in output and "AG Argon" in output
    assert "UNTRUSTED" not in output and "Traceback" not in output


@pytest.mark.parametrize("failure", ["missing", "unreadable", "non_utf8"])
def test_unreadable_usage_key_is_sanitized_without_fetch(setup, monkeypatch, failure, capsys):
    config, cache, _, key, fetch = setup
    if failure == "missing":
        key.unlink()
    elif failure == "non_utf8":
        key.write_bytes(b"\xff\xfePRIVATE")
    else:
        original = Path.read_text

        def unreadable(path, *args, **kwargs):
            if path == key:
                raise PermissionError(SECRET)
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", unreadable)
    output = o.omniroute_lines(config, cache, now=NOW)
    assert output.startswith(HEADER) and "n/a" in output
    assert SECRET not in output and str(key) not in output and "PRIVATE" not in output
    fetch.assert_not_called()
    assert capsys.readouterr() == ("", "")


def test_unrepresentable_stale_receipt_does_not_hide_fresh_healthy_account(setup, snapshot):
    config, cache, _, _, _ = setup
    o.omniroute_lines(config, cache, now=NOW)
    stored = json.loads(cache.read_text())
    records = next(
        value
        for value in stored.values()
        if isinstance(value, dict) and "test-claude-connection" in value
    )
    records["test-claude-connection"]["received_at"] = -1e99
    cache.write_text(json.dumps(stored))
    item, _ = selected(snapshot, "claude")
    snapshot["providers"].remove(item)
    output = o.omniroute_lines(config, cache, now=NOW + 60)
    assert "selected connection unavailable" in output
    assert "session  78%" in output and "AG Argon" in output
    assert "session   1%" not in output


def run(setup, snapshot, mutate, now=NOW):
    config, cache, _, _, _ = setup
    item, _ = selected(snapshot, "agy")
    mutate(item["quotas"])
    return o.omniroute_lines(config, cache, now=now)


def test_missing_gemini_weekly_only_blanks_that_window(setup, snapshot):
    output = run(setup, snapshot, lambda q: q.pop("gemini_weekly"))
    lines = ag_lines(output)
    assert lines["AG Gemini"] == row("AG Gemini", (18.02083, "2026-10-19T05:15:15Z"), None)
    assert (
        lines["AG Claude/GPT"] == FRESH["AG Claude/GPT"] and lines["AG Argon"] == FRESH["AG Argon"]
    )
    assert "n/a" not in output and "stale" not in output


def test_missing_argon_weekly_fails_only_argon_row(setup, snapshot):
    output = run(setup, snapshot, lambda q: q.pop("gemini_4_argon_weekly"))
    lines = ag_lines(output)
    assert lines["AG Argon"] == fmt_line("AG Argon", QUOTA_NA)
    assert lines["AG Gemini"] == FRESH["AG Gemini"]
    assert lines["AG Claude/GPT"] == FRESH["AG Claude/GPT"]
    assert "Antigravity" not in output


def test_missing_claude_gpt_weekly_blanks_that_window(setup, snapshot):
    lines = ag_lines(run(setup, snapshot, lambda q: q.pop("claude_gpt_weekly")))
    assert lines["AG Claude/GPT"] == row("AG Claude/GPT", (0.0012, "2026-10-19T07:26:06Z"), None)
    assert lines["AG Gemini"] == FRESH["AG Gemini"]


def test_current_live_shape_without_gemini_weekly_and_argon_keeps_other_rows(setup, snapshot):
    def mutate(q):
        for key in ("gemini_weekly", "gemini_4_argon_weekly", "gemini-4-argon-high"):
            del q[key]

    output = run(setup, snapshot, mutate)
    lines = ag_lines(output)
    assert lines["AG Gemini"] == row("AG Gemini", (18.02083, "2026-10-19T05:15:15Z"), None)
    assert lines["AG Claude/GPT"] == FRESH["AG Claude/GPT"]
    assert lines["AG Argon"] == fmt_line("AG Argon", QUOTA_NA)
    assert "Antigravity" not in output


def test_malformed_key_fails_only_that_row(setup, snapshot):
    output = run(setup, snapshot, lambda q: q["claude_gpt_weekly"].update(remainingPercentage="x"))
    lines = ag_lines(output)
    assert lines["AG Claude/GPT"] == fmt_line("AG Claude/GPT", QUOTA_NA)
    assert lines["AG Gemini"] == FRESH["AG Gemini"] and lines["AG Argon"] == FRESH["AG Argon"]


def test_failed_row_uses_cached_row_with_stale_marker(setup, snapshot):
    config, cache, _, _, _ = setup
    o.omniroute_lines(config, cache, now=NOW)
    output = run(setup, snapshot, lambda q: q.pop("gemini_4_argon_weekly"), now=NOW + 60)
    marker = datetime.fromtimestamp(NOW).strftime("%Y-%m-%d %H:%M")
    lines = ag_lines(output)
    assert lines["AG Argon"] == FRESH["AG Argon"] + f" · stale (received {marker})"
    assert fmt_line("AG Argon", QUOTA_NA) not in output
    assert lines["AG Gemini"] == FRESH["AG Gemini"]
    # Fresh rows refresh the cache; failed row keeps its old receipt.
    again = run(setup, snapshot, lambda q: None, now=NOW + 120)
    assert f"received {marker}" in ag_lines(again)["AG Argon"]


def test_no_line_starts_with_antigravity(setup, snapshot):
    config, cache, _, _, _ = setup
    outputs = [
        run(setup, snapshot, lambda q: q.pop("gemini_weekly")),
        run(setup, snapshot, lambda q: q.clear(), now=NOW + 60),
    ]
    snapshot["providers"] = [p for p in snapshot["providers"] if p["provider"] != "agy"]
    outputs.append(o.omniroute_lines(config, cache, now=NOW + 120))
    for output in outputs:
        assert not any(line.startswith("Antigravity") for line in output.splitlines())


@pytest.mark.parametrize("failure", ["all_rows", "missing", "mismatch"])
def test_all_ag_rows_failing_labels_error_line_ag(setup, snapshot, failure):
    config, cache, _, _, _ = setup
    item, _ = selected(snapshot, "agy")
    if failure == "all_rows":
        item["quotas"].clear()
        error = QUOTA_NA
    elif failure == "missing":
        snapshot["providers"].remove(item)
        error = "n/a (selected connection unavailable)"
    else:
        item["provider"] = "codex"
        error = "n/a (selected connection unavailable)"
    output = o.omniroute_lines(config, cache, now=NOW)
    assert fmt_line("AG", error) in output.splitlines()
    assert "Antigravity" not in output


def test_all_ag_rows_failing_keeps_stale_rows_and_ag_error(setup, snapshot):
    config, cache, _, _, _ = setup
    o.omniroute_lines(config, cache, now=NOW)
    output = run(setup, snapshot, lambda q: q.clear(), now=NOW + 60)
    marker = datetime.fromtimestamp(NOW).strftime("%Y-%m-%d %H:%M")
    lines = output.splitlines()
    for _label, fresh in FRESH.items():
        assert fresh + f" · stale (received {marker})" in lines
    assert fmt_line("AG", QUOTA_NA) in lines


def test_cache_hit_accepts_per_row_error_and_stale_lines_without_refetch(setup, snapshot):
    config, cache, _, _, fetch = setup
    o.omniroute_lines(config, cache, now=NOW)
    first = run(setup, snapshot, lambda q: q.pop("gemini_4_argon_weekly"), now=NOW + 60)
    assert fmt_line("AG Argon", QUOTA_NA) not in first  # stale row, from cache
    cached = o.omniroute_lines(config, cache, now=NOW + 90)
    assert cached == first and fetch.call_count == 2
    # No prior cache for the row: per-row error line must also survive the hit.
    cache.unlink()
    second = run(setup, snapshot, lambda q: None, now=NOW + 200)
    assert fmt_line("AG Argon", QUOTA_NA) in second.splitlines()
    assert o.omniroute_lines(config, cache, now=NOW + 230) == second
    assert fetch.call_count == 3
