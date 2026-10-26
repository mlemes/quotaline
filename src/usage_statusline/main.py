import json
import sys

from usage_statusline.antigravity import antigravity_line
from usage_statusline.claude import claude_line
from usage_statusline.codex import codex_line
from usage_statusline.omniroute import omniroute_lines

# Rows without live data: errors, stale cache, or a provider that is absent or not yet used.
UNUSABLE = ("n/a (", "stale (", "no usage yet", "usage appears after")


def _usable(text: str | None) -> list[str]:
    """Lines of text that carry live quota data."""
    return [line for line in (text or "").splitlines() if not any(m in line for m in UNUSABLE)]


def _routed() -> list[str]:
    """OmniRoute rows, or [] when it is not configured or yields no live quota row."""
    try:
        lines = _usable(omniroute_lines())
    except Exception:  # A router failure falls back to native sources.
        return []
    return lines if len(lines) > 1 else []  # The header alone is not data.


def _native() -> list[str]:
    """Native rows of every provider that is installed and has live data."""
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    lines: list[str] = []
    for source in (lambda: claude_line(data), antigravity_line, codex_line):
        try:
            lines.extend(_usable(source()))
        except Exception:  # A provider failure must not suppress the other providers.
            continue
    return lines


def main() -> None:
    """Print one line per provider that is installed and has live quota data."""
    lines = _routed() or _native()
    if lines:
        print("\n".join(lines))
