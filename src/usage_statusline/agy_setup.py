"""Find agy's token in the system keyring and save the command that prints it.

Run by install.sh. Lists only labels and attributes (public in the Secret
Service API); the secret is read once to check it, and never printed.
"""

import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable

from usage_statusline import antigravity as ag

Run = Callable[[list[str]], str]
DEST = "org.freedesktop.secrets"
MATCH = re.compile(r"antigravity|jetski|\bagy\b", re.I)
SKIP = re.compile(r"safe storage", re.I)  # the Antigravity IDE's Chromium key, not a token


def sh(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout


def prop(run: Run, path: str, iface: str, name: str) -> str:
    return run(
        ["gdbus", "call", "--session", "-d", DEST, "-o", path, "-m",
         "org.freedesktop.DBus.Properties.Get", iface, name]
    )  # fmt: skip


def list_entries(run: Run = sh) -> list[tuple[str, dict[str, str]]]:
    """(label, attributes) for every item in every keyring collection."""
    root = "/org/freedesktop/secrets"
    out = []
    cols = prop(run, root, "org.freedesktop.Secret.Service", "Collections")
    for col in re.findall(rf"'({root}/collection/[^'/]+)'", cols):
        items = prop(run, col, "org.freedesktop.Secret.Collection", "Items")
        for item in re.findall(rf"'({col}/[^']+)'", items):
            label = re.search(r"<'(.*)'>", prop(run, item, "org.freedesktop.Secret.Item", "Label"))
            attrs = prop(run, item, "org.freedesktop.Secret.Item", "Attributes")
            pairs = dict(re.findall(r"'([^']*)': '([^']*)'", attrs))
            out.append((label.group(1) if label else "", pairs))
    return out


def candidates(entries: list[tuple[str, dict[str, str]]]) -> list[tuple[str, dict[str, str]]]:
    def text(e: tuple[str, dict[str, str]]) -> str:
        return e[0] + " " + " ".join(f"{k} {v}" for k, v in e[1].items())

    return [e for e in entries if MATCH.search(text(e)) and not SKIP.search(e[0])]


def lookup_cmd(attrs: dict[str, str]) -> str:
    return "secret-tool lookup " + " ".join(shlex.quote(x) for kv in attrs.items() for x in kv)


def main(argv: list[str], run: Run = sh, which: Callable = shutil.which) -> int:
    for tool, pkg in (("secret-tool", "libsecret-tools"), ("gdbus", "libglib2.0-bin")):
        if not which(tool):
            print(f"Antigravity: skipped, {tool} not found. Run: sudo apt install {pkg}")
            return 1
    found = candidates(list_entries(run))
    pick = int(argv[argv.index("--agy-entry") + 1]) if "--agy-entry" in argv else None
    if pick is None and len(found) != 1:
        print(f"Antigravity: found {len(found)} matching keyring entries.")
        for n, (label, attrs) in enumerate(found, 1):
            print(f"  {n}. {label}  {attrs}")
        print("Run agy once to log in, or rerun ./install.sh --agy-entry N")
        return 1
    if pick is not None and not 1 <= pick <= len(found):
        print(f"Antigravity: --agy-entry must be between 1 and {len(found)}")
        return 1
    cmd = lookup_cmd(found[(pick or 1) - 1][1])
    try:
        token = ag.extract_token(run(["sh", "-c", cmd]))
    except ValueError:
        token = ""
    if not token:
        print("Antigravity: that entry holds no access token. Run agy to log in, then retry.")
        return 1
    ag.CONFIG.parent.mkdir(parents=True, exist_ok=True)
    ag.CONFIG.write_text(cmd + "\n")
    ag.CACHE.unlink(missing_ok=True)
    print(f"Antigravity: saved token command to {ag.CONFIG}")
    print(ag.antigravity_line())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
