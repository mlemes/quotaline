import json
import sys

from usage_statusline.antigravity import antigravity_line
from usage_statusline.claude import claude_line, fmt_line
from usage_statusline.codex import codex_line


def main() -> None:
    """Read the status line JSON on stdin and print one line per provider."""
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
