import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from usage_statusline import main as m
from usage_statusline.claude import claude_line
from usage_statusline.codex import codex_line, latest_rate_limits

NOW = 1_800_000_000.0
FUTURE = NOW + 3600


def event(limits, ts="2026-09-28T12:00:00Z") -> str:
    p = {"type": "token_count", "info": {}, "rate_limits": limits}
    return json.dumps({"timestamp": ts, "type": "event_msg", "payload": p})


def win(pct, minutes, resets_at=FUTURE) -> dict:
    return {"used_percent": pct, "window_minutes": minutes, "resets_at": resets_at}


def session(root: Path, lines: list[str], day="2026/09/28", name="rollout-a.jsonl", mtime=None):
    d = root / day
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text("\n".join(lines) + "\n")
    if mtime:
        os.utime(f, (mtime, mtime))
    return f


def limits(**kw) -> dict:
    return {"limit_id": "codex", "primary": None, "secondary": None, **kw}


def test_paid_plan_two_windows(tmp_path: Path) -> None:
    session(tmp_path, [event(limits(primary=win(12, 300), secondary=win(34, 10080)))])
    line = codex_line(tmp_path, NOW)
    assert line.startswith("Codex")
    assert "session  12%" in line and "week  34%" in line


def test_free_plan_30d_in_second_column(tmp_path: Path) -> None:
    session(tmp_path, [event(limits(primary=win(5, 43200)))])
    line = codex_line(tmp_path, NOW)
    assert "session   --" in line and "30d    5%" in line
    assert line.index("|") < line.index("30d")


def test_rollover_shows_zero_and_dashes(tmp_path: Path) -> None:
    session(tmp_path, [event(limits(primary=win(80, 300, NOW - 10), secondary=win(34, 10080)))])
    line = codex_line(tmp_path, NOW)
    assert "session   0% · resets --" in line
    assert line.index("|") == line.index("session") + len("session   0% · resets --       ") + 1


def test_alignment_matches_claude(tmp_path: Path) -> None:
    reset = 1_900_000_000
    session(
        tmp_path, [event(limits(primary=win(100, 300, reset), secondary=win(100, 10080, reset)))]
    )
    codex = codex_line(tmp_path, NOW)
    w = {"used_percentage": 100, "resets_at": reset}
    claude = claude_line({"rate_limits": {"five_hour": w, "seven_day": w}})
    for mark in ("session", "·", "|", "week"):
        assert codex.index(mark) == claude.index(mark), mark
    free = tmp_path / "free"
    session(free, [event(limits(primary=win(100, 43200, reset)))])
    assert codex_line(free, NOW).index("|") == claude.index("|")
    roll = tmp_path / "roll"
    session(roll, [event(limits(primary=win(1, 300, 5), secondary=win(1, 10080, 5)))])
    line = codex_line(roll, NOW)
    assert [line.index(m) for m in ("·", "|")] == [claude.index(m) for m in ("·", "|")]
    assert line.index("week") == claude.index("week")


def test_missing_dir_is_none_and_empty_is_no_usage(tmp_path: Path) -> None:
    assert codex_line(tmp_path / "nope", NOW) is None
    session(tmp_path, ['{"type": "other"}'])
    assert "no usage yet" in codex_line(tmp_path, NOW)


def test_skips_null_and_foreign_limits(tmp_path: Path) -> None:
    lines = [
        event(limits(primary=win(11, 300))),
        event({"limit_id": "other", "primary": win(99, 300)}),
        event(None),
        "not json",
    ]
    session(tmp_path, lines)
    assert latest_rate_limits(tmp_path)["primary"]["used_percent"] == 11
    session(tmp_path, [event({"primary": win(7, 300)})], name="rollout-b.jsonl")
    assert latest_rate_limits(tmp_path) is not None


def test_resets_in_seconds_fallback(tmp_path: Path) -> None:
    w = {"used_percent": 3, "window_minutes": 300, "resets_in_seconds": 600}
    session(tmp_path, [event(limits(primary=w), ts="2026-09-28T12:00:00Z")])
    got = latest_rate_limits(tmp_path)["primary"]["resets_at"]
    assert got == datetime(2026, 9, 28, 12, 10, tzinfo=UTC).timestamp()


def test_only_tail_read(tmp_path: Path) -> None:
    junk = ["x" * 1000] * 400  # ~400 KB before the event
    session(
        tmp_path, [event(limits(primary=win(1, 300)))] + junk + [event(limits(primary=win(9, 300)))]
    )
    assert latest_rate_limits(tmp_path)["primary"]["used_percent"] == 9


def test_newest_file_wins(tmp_path: Path) -> None:
    session(tmp_path, [event(limits(primary=win(1, 300)))], name="rollout-a.jsonl", mtime=100)
    session(tmp_path, [event(limits(primary=win(2, 300)))], name="rollout-b.jsonl", mtime=200)
    assert latest_rate_limits(tmp_path)["primary"]["used_percent"] == 2


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    sessions: Path,
) -> list[str]:
    claude_limits = {"five_hour": {"used_percentage": 10, "resets_at": FUTURE}}
    monkeypatch.setattr(m, "omniroute_lines", lambda: None)
    monkeypatch.setattr(m, "antigravity_line", lambda: None)
    monkeypatch.setattr(m, "opencode_line", lambda: None)
    monkeypatch.setattr(m, "codex_line", lambda: codex_line(sessions, NOW))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"rate_limits": claude_limits})))
    m.main()
    return capsys.readouterr().out.splitlines()


@pytest.mark.parametrize(
    "empty_limits",
    [
        limits(),
        limits(
            primary={"used_percent": None, "window_minutes": 300, "resets_at": FUTURE},
            secondary={"used_percent": 25, "window_minutes": 10080, "resets_at": None},
        ),
        limits(
            primary={"used_percent": 15, "window_minutes": None, "resets_at": FUTURE},
            secondary={},
        ),
    ],
    ids=["null-windows", "missing-usage-and-reset", "missing-minutes-and-empty"],
)
def test_empty_or_unusable_latest_snapshot_hides_codex_while_claude_shows(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    empty_limits: dict,
) -> None:
    older_usage = event(limits(primary=win(42, 300)), ts="2026-09-28T11:00:00Z")
    session(tmp_path, [older_usage, event(empty_limits)])
    lines = _run_main(monkeypatch, capsys, tmp_path)
    assert len(lines) == 1
    assert lines[0].startswith("Claude") and "10%" in lines[0]


def test_real_zero_with_future_reset_remains_visible(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    session(tmp_path, [event(limits(primary=win(0, 300, FUTURE), secondary=win(0, 10080, FUTURE)))])
    lines = _run_main(monkeypatch, capsys, tmp_path)
    assert len(lines) == 2
    assert lines[0].startswith("Claude")
    reset_text = datetime.fromtimestamp(FUTURE).astimezone().strftime("%a %H:%M")
    assert lines[1].startswith("Codex")
    assert f"session   0% · resets {reset_text}" in lines[1]
    assert f"week   0% · resets {reset_text}" in lines[1]


def test_expired_usage_rolls_to_zero_with_dashes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    session(
        tmp_path, [event(limits(primary=win(80, 300, NOW - 10), secondary=win(34, 10080, FUTURE)))]
    )
    lines = _run_main(monkeypatch, capsys, tmp_path)
    assert len(lines) == 2
    assert lines[1].startswith("Codex")
    assert "session   0% · resets --" in lines[1]
    assert "week  34%" in lines[1]


@pytest.mark.parametrize(
    ("codex_limits", "present_part", "missing_part", "second_label"),
    [
        (limits(primary=win(12, 300, FUTURE)), "session  12%", "week   --", "week"),
        (limits(secondary=win(34, 10080, FUTURE)), "week  34%", "session   --", "week"),
        (limits(primary=win(5, 43200, FUTURE)), "30d    5%", "session   --", "30d"),
    ],
    ids=["session-only", "week-only", "30d-only"],
)
def test_single_usable_window_aligns_with_populated_row_and_retains_missing_counterpart(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    codex_limits: dict,
    present_part: str,
    missing_part: str,
    second_label: str,
) -> None:
    session(tmp_path, [event(codex_limits)])
    lines = _run_main(monkeypatch, capsys, tmp_path)
    assert len(lines) == 2
    claude, codex = lines
    assert present_part in codex
    assert missing_part in codex
    assert codex.index("|") == claude.index("|")
    assert codex.index(second_label) == claude.index("week")


@pytest.mark.parametrize(
    ("primary", "secondary", "present_part", "missing_part"),
    [
        (win(5, 43200), win(None, 10080), "30d    5%", "session   --"),
        (win(14, 300), win(None, 300), "session  14%", "week   --"),
    ],
    ids=["longer-slot", "session-slot"],
)
def test_unusable_window_cannot_replace_usable_slot(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    primary: dict,
    secondary: dict,
    present_part: str,
    missing_part: str,
) -> None:
    session(tmp_path, [event(limits(primary=primary, secondary=secondary))])
    claude, codex = _run_main(monkeypatch, capsys, tmp_path)
    assert present_part in codex
    assert missing_part in codex
    assert codex.index("|") == claude.index("|")
