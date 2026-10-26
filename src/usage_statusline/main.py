import json
import sys

from usage_statusline.antigravity import antigravity_line
from usage_statusline.claude import claude_line, fmt_line
from usage_statusline.codex import codex_line
from usage_statusline.omniroute import FETCH_FAILED, omniroute_lines


def main() -> None:
    """Read the status line JSON on stdin and print one line per provider."""
    try:
        routed = omniroute_lines()
    except Exception:  # Router mode never falls back to native sources.
        print(fmt_line("OmniRoute", "n/a (fetch failed)"))
        return
    if routed is not None:
        head = routed.splitlines()[:2]
        if not any(line.endswith(f"n/a ({FETCH_FAILED})") for line in head[1:]):
            print(routed)
            return
        # Router down: drop its stale rows so native rows are not duplicated.
        print("\n".join(head))
        print(fmt_line("Native", "OmniRoute unavailable; unmapped local sources"))
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    try:
        print(claude_line(data))
    except Exception as error:  # Malformed Claude input must not suppress other providers.
        print(fmt_line("Claude", f"n/a ({type(error).__name__})"))
    try:
        print(antigravity_line())
    except Exception as error:  # A provider failure must not suppress the other providers.
        print(fmt_line("Antigravity", f"n/a ({type(error).__name__})"))
    codex = codex_line()
    if codex is not None:
        print(codex)
