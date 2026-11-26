"""Replay the Codex quota fix from PR #14 (issue #12) against a supplied checkout."""

import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

NOW = 1_800_000_000
FUTURE = NOW + 3600


def run(checkout: Path) -> int:
    sys.path.insert(0, str(checkout.resolve() / "src"))
    from usage_statusline import main as entry
    from usage_statusline.codex import codex_line

    def record(primary, secondary):
        limits = {"limit_id": "codex", "primary": primary, "secondary": secondary}
        return json.dumps(
            {"type": "event_msg", "payload": {"type": "token_count", "rate_limits": limits}}
        )

    def window(pct, minutes, reset=FUTURE):
        return {"used_percent": pct, "window_minutes": minutes, "resets_at": reset}

    peer = {"rate_limits": {"five_hour": {"used_percentage": 42, "resets_at": FUTURE}}}
    with TemporaryDirectory() as d:
        sessions = Path(d)
        day = sessions / "2026/01/01"
        day.mkdir(parents=True)
        sample = day / "rollout-synthetic.jsonl"

        def render(records, claude=None):
            sample.write_text("\n".join(records) + "\n", encoding="utf-8")
            # main() hides provider errors. Surface them before checking for an absent row.
            codex = codex_line(sessions, NOW)
            if codex and "n/a (" in codex:
                raise RuntimeError(f"Codex failed to read the synthetic session: {codex}")
            with (
                patch.multiple(
                    entry,
                    omniroute_lines=lambda: None,
                    antigravity_line=lambda: None,
                    opencode_line=lambda: None,
                    codex_line=lambda: codex,
                ),
                patch.object(sys, "stdin", io.StringIO(json.dumps(claude or {}))),
                redirect_stdout(out := io.StringIO()),
            ):
                entry.main()
            return out.getvalue().splitlines()

        paid = record(window(12, 300), window(41, 10080))
        blank = record(None, None)
        empty = render([paid, blank])
        mixed = render([paid, blank], peer)
        zero = render([record(window(0, 300), None)])
        rolled = render([record(window(73, 300, NOW - 1), None)])
        monthly = render([record(window(5, 43200), None)])
        complete = render([paid])
        collision = render([record(window(5, 43200), window(None, 10080))])
        known_reset = datetime.fromtimestamp(FUTURE).strftime("%a %H:%M")
        checks = {
            "newest empty record hides Codex": not empty,
            "only the valid Claude peer remains": len(mixed) == 1
            and mixed[0].startswith("Claude ")
            and "42%" in mixed[0],
            "reported zero and known reset survive": len(zero) == 1
            and f"session   0% · resets {known_reset}" in zero[0],
            "expired window retains rollover zero": len(rolled) == 1
            and "session   0% · resets --" in rolled[0],
            "single 30-day reading keeps column and label": (
                len(monthly) == len(complete) == 1
                and "session   --" in monthly[0]
                and "30d    5%" in monthly[0]
                and monthly[0].find("|") == complete[0].find("|") != -1
            ),
            "an unusable weekly window cannot erase a valid 30-day reading": (
                collision == monthly and len(collision) == 1
            ),
        }
    for label, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}  {label}")
    print(f"{sum(checks.values())}/{len(checks)} checks passed")
    return int(not all(checks.values()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="path to the candidate Quotaline checkout")
    args = parser.parse_args()
    if not (args.checkout / "src/usage_statusline/__init__.py").is_file():
        parser.error(f"no Quotaline package in {args.checkout}/src")
    raise SystemExit(run(args.checkout))
