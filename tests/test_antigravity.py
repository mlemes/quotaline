import io
import json
from pathlib import Path

import pytest

from usage_statusline import antigravity as ag

RESP = {
    "models": {
        "gemini-3.8-flash-high": {
            "quotaInfo": {"remainingFraction": 0.75, "resetTime": "2026-09-27T18:00:00Z"}
        },
        "gemini-3.8-flash-low": {
            "quotaInfo": {"remainingFraction": 0.9, "resetTime": "2026-09-27T18:00:00Z"}
        },
        "gemini-3.1-pro-high": {"quotaInfo": {"resetTime": "2026-09-28T01:00:00Z"}},
        "claude-opus-4-6-thinking": {"quotaInfo": {"remainingFraction": 1.0}},
        "gpt-oss-120b-medium": {
            "quotaInfo": {"remainingFraction": 0.5, "resetTime": "2026-09-27T18:00:00Z"}
        },
    }
}


def test_parse_keeps_most_used_model_per_family() -> None:
    q = ag.parse_quota(RESP)
    assert set(q) == {"Flash", "Pro"}  # Claude has no resetTime, GPT-OSS not shown
    assert q["Flash"][0] == pytest.approx(25)
    assert q["Pro"][0] == pytest.approx(100)  # missing remainingFraction means exhausted


def test_format_line_orders_families() -> None:
    line = ag.format_line(ag.parse_quota(RESP))
    assert line.startswith("Antigravity")
    assert line.index("Flash 25%") < line.index("Pro 100%")


def test_empty_response() -> None:
    assert "no quota data" in ag.format_line(ag.parse_quota({}))


def test_no_token_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", raising=False)
    monkeypatch.setattr(ag, "CONFIG", tmp_path / "missing")
    assert "no token command" in ag.fetch_line()


def test_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "true")
    assert "no token" in ag.fetch_line()


def test_fetch_sends_token_and_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = {}

    def fake_urlopen(req, timeout):
        sent.update(req.headers)
        return io.BytesIO(json.dumps(RESP).encode())

    monkeypatch.setenv("USAGE_STATUSLINE_AGY_TOKEN_CMD", "echo ya29.abc")
    monkeypatch.setattr(ag.urllib.request, "urlopen", fake_urlopen)
    assert "Flash 25%" in ag.fetch_line()
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
