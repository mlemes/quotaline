import io
import json
from pathlib import Path

import pytest

from usage_statusline import antigravity as ag

# Shape of a real retrieveUserQuotaSummary response (2026-09-27), trimmed.
RESP = {
    "groups": [
        {
            "displayName": "Gemini Models",
            "buckets": [
                {
                    "bucketId": "gemini-weekly",
                    "window": "weekly",
                    "resetTime": "2026-09-29T02:28:05Z",
                    "remainingFraction": 0.8551896,
                },
                {
                    "bucketId": "gemini-5h",
                    "window": "5h",
                    "resetTime": "2026-09-27T19:00:27Z",
                    "remainingFraction": 1,
                },
            ],
        },
        {
            "displayName": "Claude and GPT models",
            "buckets": [
                {"bucketId": "3p-weekly", "window": "weekly", "resetTime": "2026-10-04T03:50:20Z"},
                {
                    "bucketId": "3p-5h",
                    "window": "5h",
                    "resetTime": "2026-09-27T19:00:27Z",
                    "remainingFraction": 0.75,
                },
            ],
        },
        {"displayName": "Future Group", "buckets": [{"bucketId": "new-5h", "window": "5h"}]},
    ]
}


def sent_headers(req) -> dict:
    """Headers as sent, whether set normally or as unredirected."""
    return {**req.headers, **req.unredirected_hdrs}


def test_parse_summary_one_entry_per_group() -> None:
    groups = ag.parse_summary(RESP)
    assert [g[0] for g in groups] == ["AG Gemini", "AG Claude/GPT", "Future Group"]
    gemini, claude, future = groups
    assert gemini[1][0] == pytest.approx(0) and gemini[2][0] == pytest.approx(14.48, abs=0.01)
    assert claude[1][0] == pytest.approx(25)
    assert claude[2][0] == pytest.approx(100)  # missing remainingFraction means exhausted
    assert future[1] is None and future[2] is None  # bucket without resetTime is skipped


@pytest.mark.parametrize(
    "bad", [-0.1, 1.5, True, False, "0.5", None, float("nan"), float("inf"), float("-inf")]
)
def test_parse_summary_skips_invalid_remaining_fraction(bad) -> None:
    resp = {
        "groups": [
            {
                "displayName": "Gemini Models",
                "buckets": [
                    {
                        "window": "5h",
                        "resetTime": "2026-09-27T19:00:27Z",
                        "remainingFraction": bad,
                    },
                    {
                        "window": "weekly",
                        "resetTime": "2026-09-29T02:28:05Z",
                        "remainingFraction": 0.5,
                    },
                ],
            }
        ]
    }
    (_, session, weekly) = ag.parse_summary(resp)[0]
    assert session is None
    assert weekly is not None and weekly[0] == pytest.approx(50)


def test_format_lines_one_line_per_group() -> None:
    lines = ag.format_lines(ag.parse_summary(RESP)).splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("AG Gemini      session   0%")
    assert "week  14%" in lines[0]
    assert lines[1].startswith("AG Claude/GPT  session  25%")


def test_columns_align_across_lines() -> None:
    lines = ag.format_lines(ag.parse_summary(RESP)).splitlines()[:2]
    for mark in ("session", "·", "|", "week"):
        assert len({line.index(mark) for line in lines}) == 1, mark


def test_empty_response() -> None:
    assert "no quota data" in ag.format_lines(ag.parse_summary({}))


def test_no_token_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", raising=False)
    monkeypatch.setattr(ag, "CONFIG", tmp_path / "missing")
    assert "no token command" in ag.fetch_line()


def test_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "true")
    assert "no token" in ag.fetch_line()


def test_token_command_runs_without_a_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = {}

    def fake_urlopen(req, timeout):
        sent.update(sent_headers(req))
        return io.BytesIO(json.dumps(RESP).encode())

    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo 'ya29.abc' | cat")
    monkeypatch.setattr(ag.urllib.request, "urlopen", fake_urlopen)
    ag.fetch_line()
    assert sent["Authorization"] == "Bearer ya29.abc | cat"  # echo got the pipe as text
    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "  ")
    assert "no token command" in ag.fetch_line()


def test_fetch_sends_token_and_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = {}

    def fake_urlopen(req, timeout):
        sent.update(sent_headers(req))
        return io.BytesIO(json.dumps(RESP).encode())

    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo ya29.abc")
    monkeypatch.setattr(ag.urllib.request, "urlopen", fake_urlopen)
    assert "AG Claude/GPT  session  25%" in ag.fetch_line()
    assert sent["Authorization"] == "Bearer ya29.abc"
    assert sent["User-agent"] == "antigravity"  # default Python-urllib gets HTTP 403


def test_authorization_is_unredirected(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = []

    def fake_urlopen(req, timeout):
        requests.append(req)
        return io.BytesIO(json.dumps(RESP).encode())

    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo ya29.abc")
    monkeypatch.setattr(ag.urllib.request, "urlopen", fake_urlopen)
    ag.fetch_line()
    assert requests
    for req in requests:
        assert "Authorization" not in req.headers  # redirects copy req.headers
        assert req.unredirected_hdrs["Authorization"] == "Bearer ya29.abc"


def test_cache_is_reused_within_ttl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setattr(ag, "fetch_line", lambda: calls.append(1) or "Antigravity  x")
    cache = tmp_path / "c" / "antigravity.json"
    assert ag.antigravity_line(cache, now=1000) == "Antigravity  x"
    assert ag.antigravity_line(cache, now=1000 + ag.CACHE_TTL - 1) == "Antigravity  x"
    assert len(calls) == 1
    ag.antigravity_line(cache, now=1000 + ag.CACHE_TTL)
    assert len(calls) == 2
    assert json.loads(cache.read_text())["fetched_at"] == 1000 + ag.CACHE_TTL


def test_corrupt_cache_refetches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ag, "fetch_line", lambda: "Antigravity  y")
    cache = tmp_path / "antigravity.json"
    cache.write_text("not json")
    assert ag.antigravity_line(cache, now=0) == "Antigravity  y"


MODELS = {
    "models": {
        "gemini-flash": {
            "displayName": "Gemini Flash",
            "quotaInfo": {"remainingFraction": 0.75, "resetTime": "2026-10-18T05:22:59Z"},
        },
        "gemini-pro": {
            "displayName": "Gemini Pro",
            "quotaInfo": {"remainingFraction": 0.75, "resetTime": "2026-10-18T05:22:59Z"},
        },
    }
}


def test_missing_gemini_uses_model_quota(monkeypatch):
    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo test-token")

    def respond(req, timeout):
        body = (
            MODELS
            if req.full_url.endswith("fetchAvailableModels")
            else {"groups": [RESP["groups"][1]]}
        )
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(ag.urllib.request, "urlopen", respond)
    lines = ag.fetch_line().splitlines()
    assert len(lines) == 2
    assert "AG Claude/GPT" in lines[0]
    assert "AG Gemini" in lines[1] and "quota  25%" in lines[1]
    assert "week" not in lines[1]


def test_model_quota_missing_is_unknown():
    assert ag.parse_models({"models": {"gemini": {"displayName": "Gemini"}}}) == []


def test_distinct_model_quotas_stay_distinct():
    models = json.loads(json.dumps(MODELS))
    models["models"]["gemini-pro"]["quotaInfo"]["remainingFraction"] = 0.5
    lines = ag.parse_models(models)
    assert len(lines) == 2
    assert "Gemini Flash" in lines[0] and "25%" in lines[0]
    assert "Gemini Pro" in lines[1] and "50%" in lines[1]


def test_401_refreshes_with_agy_once(monkeypatch):
    import urllib.error

    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo test-token")
    attempts = []

    def respond(req, timeout):
        attempts.append(req)
        if len(attempts) == 1:
            raise urllib.error.HTTPError(req.full_url, 401, "expired", {}, None)
        return io.BytesIO(json.dumps(RESP).encode())

    refreshed = []
    monkeypatch.setattr(ag, "refresh_login", lambda: refreshed.append(True) or True, raising=False)
    monkeypatch.setattr(ag.urllib.request, "urlopen", respond)
    assert "AG Gemini" in ag.fetch_line()
    assert refreshed == [True]
    assert len(attempts) == 2


def test_last_success_survives_fetch_error(monkeypatch, tmp_path):
    cache = tmp_path / "cache.json"
    good = ag.format_lines(ag.parse_summary(RESP))
    monkeypatch.setattr(ag, "fetch_line", lambda: good)
    ag.antigravity_line(cache, now=1000)
    monkeypatch.setattr(ag, "fetch_line", lambda: "Antigravity    n/a (HTTP 401)")
    line = ag.antigravity_line(cache, now=1060)
    assert "AG Gemini" in line and "stale" in line and "HTTP 401" in line
    assert "stale" in ag.antigravity_line(cache, now=1061)


def test_partial_fetch_preserves_missing_group(monkeypatch, tmp_path):
    cache = tmp_path / "cache.json"
    monkeypatch.setattr(ag, "fetch_line", lambda: ag.format_lines(ag.parse_summary(RESP)))
    ag.antigravity_line(cache, now=1000)
    monkeypatch.setattr(
        ag,
        "fetch_line",
        lambda: (
            ag.format_lines(ag.parse_summary({"groups": [RESP["groups"][1]]}))
            + "\nAG Gemini      n/a (fetch failed)"
        ),
    )
    line = ag.antigravity_line(cache, now=1060)
    assert "AG Gemini      session" in line and "stale" in line
    claude = next(row for row in line.splitlines() if row.startswith("AG Claude"))
    assert "stale" not in claude


@pytest.mark.parametrize("contents", ["null", "[]", '{"fetched_at":"bad","line":1}'])
def test_wrong_cache_shape_refetches(monkeypatch, tmp_path, contents):
    cache = tmp_path / "cache.json"
    cache.write_text(contents)
    monkeypatch.setattr(ag, "fetch_line", lambda: "Antigravity  y")
    assert ag.antigravity_line(cache, now=1000) == "Antigravity  y"


def test_cache_write_failure_keeps_fresh_output(monkeypatch, tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("")
    monkeypatch.setattr(ag, "fetch_line", lambda: "Antigravity  y")
    assert ag.antigravity_line(blocker / "cache.json", now=1000) == "Antigravity  y"


def test_model_endpoint_failure_keeps_summary(monkeypatch):
    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo test-token")

    def respond(req, timeout):
        if req.full_url.endswith("fetchAvailableModels"):
            raise OSError("offline")
        return io.BytesIO(json.dumps({"groups": [RESP["groups"][1]]}).encode())

    monkeypatch.setattr(ag.urllib.request, "urlopen", respond)
    result = ag.fetch_line()
    assert "AG Claude/GPT  session  25%" in result
    assert "AG Gemini" in result and "fetch failed" in result


def test_summary_endpoint_failure_still_fetches_gemini(monkeypatch):
    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo test-token")

    def respond(req, timeout):
        if req.full_url.endswith("retrieveUserQuotaSummary"):
            raise OSError("offline")
        return io.BytesIO(json.dumps(MODELS).encode())

    monkeypatch.setattr(ag.urllib.request, "urlopen", respond)
    assert "AG Gemini      quota  25%" in ag.fetch_line()


@pytest.mark.parametrize("code,refresh_count", [(401, 1), (403, 0)])
def test_auth_failure_refresh_is_bounded(monkeypatch, code, refresh_count):
    import urllib.error

    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo test-token")

    def respond(req, timeout):
        raise urllib.error.HTTPError(req.full_url, code, "denied", {}, None)

    refreshed = []
    monkeypatch.setattr(ag.urllib.request, "urlopen", respond)
    monkeypatch.setattr(ag, "refresh_login", lambda: refreshed.append(True) or True)
    assert f"HTTP {code}" in ag.fetch_line()
    assert len(refreshed) == refresh_count


def test_401_rereads_refreshed_token(monkeypatch):
    import urllib.error
    from subprocess import CompletedProcess

    tokens = iter(["old-token", "new-token"])
    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "token-reader")
    monkeypatch.setattr(
        ag.subprocess, "run", lambda *a, **kw: CompletedProcess(a, 0, stdout=next(tokens))
    )

    def respond(req, timeout):
        if sent_headers(req)["Authorization"] == "Bearer old-token":
            raise urllib.error.HTTPError(req.full_url, 401, "expired", {}, None)
        assert sent_headers(req)["Authorization"] == "Bearer new-token"
        return io.BytesIO(json.dumps(RESP).encode())

    monkeypatch.setattr(ag, "refresh_login", lambda: True)
    monkeypatch.setattr(ag.urllib.request, "urlopen", respond)
    assert "AG Gemini" in ag.fetch_line()


def test_refresh_timeout_is_bounded(monkeypatch, tmp_path):
    executable = tmp_path / "agy"
    executable.write_text("#!/bin/sh\nsleep 60\n")
    executable.chmod(0o700)
    monkeypatch.setattr(ag.shutil, "which", lambda name: str(executable))
    monkeypatch.setattr(ag, "REFRESH_TIMEOUT", 0.05)
    assert ag.refresh_login() is False


def test_refresh_missing_agy(monkeypatch):
    monkeypatch.setattr(ag.shutil, "which", lambda name: None)
    assert ag.refresh_login() is False


@pytest.mark.parametrize("body", [None, [], {"models": []}, {"models": {"gemini": None}}])
def test_malformed_model_response_keeps_summary(monkeypatch, body):
    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo test-token")

    def respond(req, timeout):
        data = (
            body
            if req.full_url.endswith("fetchAvailableModels")
            else {"groups": [RESP["groups"][1]]}
        )
        return io.BytesIO(json.dumps(data).encode())

    monkeypatch.setattr(ag.urllib.request, "urlopen", respond)
    result = ag.fetch_line()
    assert "AG Claude/GPT" in result and "AG Gemini" in result


def test_legacy_cache_preserves_success_on_error(monkeypatch, tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"fetched_at": 1000, "line": "AG Gemini      quota  25%"}))
    monkeypatch.setattr(ag, "fetch_line", lambda: "Antigravity    n/a (HTTP 401)")
    result = ag.antigravity_line(cache, now=1060)
    assert "AG Gemini      quota  25%" in result and "stale" in result


def test_cache_replace_failure_leaves_old_cache(monkeypatch, tmp_path):
    cache = tmp_path / "cache.json"
    original = json.dumps({"fetched_at": 1000, "line": "old"})
    cache.write_text(original)

    def denied(*args):
        raise PermissionError("read-only")

    monkeypatch.setattr(Path, "replace", denied)
    monkeypatch.setattr(ag, "fetch_line", lambda: "Antigravity  y")
    assert ag.antigravity_line(cache, now=1060) == "Antigravity  y"
    assert cache.read_text() == original
    assert list(tmp_path.iterdir()) == [cache]


def test_token_reread_timeout_keeps_summary(monkeypatch):
    import subprocess
    import urllib.error

    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo test-token")
    runs = 0

    def token(*args, **kwargs):
        nonlocal runs
        runs += 1
        if runs > 1:
            raise subprocess.TimeoutExpired("token-reader", 2)
        return subprocess.CompletedProcess(args, 0, stdout="test-token")

    def respond(req, timeout):
        if req.full_url.endswith("fetchAvailableModels"):
            raise urllib.error.HTTPError(req.full_url, 401, "expired", {}, None)
        return io.BytesIO(json.dumps({"groups": [RESP["groups"][1]]}).encode())

    monkeypatch.setattr(ag.subprocess, "run", token)
    monkeypatch.setattr(ag, "refresh_login", lambda: True)
    monkeypatch.setattr(ag.urllib.request, "urlopen", respond)
    result = ag.fetch_line()
    assert "AG Claude/GPT  session  25%" in result
    assert "AG Gemini" in result and "fetch failed" in result
