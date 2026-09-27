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


def test_parse_summary_one_entry_per_group() -> None:
    groups = ag.parse_summary(RESP)
    assert [g[0] for g in groups] == ["AG Gemini", "AG Claude/GPT", "Future Group"]
    gemini, claude, future = groups
    assert gemini[1][0] == pytest.approx(0) and gemini[2][0] == pytest.approx(14.48, abs=0.01)
    assert claude[1][0] == pytest.approx(25)
    assert claude[2][0] == pytest.approx(100)  # missing remainingFraction means exhausted
    assert future[1] is None and future[2] is None  # bucket without resetTime is skipped


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
        sent.update(req.headers)
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
        sent.update(req.headers)
        return io.BytesIO(json.dumps(RESP).encode())

    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo ya29.abc")
    monkeypatch.setattr(ag.urllib.request, "urlopen", fake_urlopen)
    assert "AG Claude/GPT  session  25%" in ag.fetch_line()
    assert sent["Authorization"] == "Bearer ya29.abc"
    assert sent["User-agent"] == "antigravity"  # default Python-urllib gets HTTP 403


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
