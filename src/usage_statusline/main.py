import json
import sys

from usage_statusline.antigravity import antigravity_line
from usage_statusline.claude import claude_line
from usage_statusline.codex import codex_line


def main() -> None:
    """Read the status line JSON on stdin and print one line per provider."""
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    print(claude_line(data))
    print(antigravity_line())
    codex = codex_line()
    if codex is not None:
        print(codex)
