"""Add or remove the statusLine entry in Claude Code's settings.json. Run by install.sh.

Usage: python3 -m usage_statusline.settings_entry SETTINGS_PATH COMMAND (install|--uninstall)
Touches only the statusLine key, and removes it only if it still runs COMMAND.
"""

import json
import sys


def update(settings: dict, cmd: str, mode: str) -> str | None:
    """Change settings in place; return a message, or None when nothing changed."""
    current = (settings.get("statusLine") or {}).get("command")
    if mode == "--uninstall":
        if current != cmd:
            return None
        del settings["statusLine"]
        return "Removed usage-statusline from"
    settings["statusLine"] = {"type": "command", "command": cmd, "refreshInterval": 60}
    if current and current != cmd:
        return f"Replaced the statusLine command {current} in"
    return "Installed usage-statusline in"


def main(argv: list[str]) -> int:
    path, cmd, mode = argv
    with open(path) as f:
        settings = json.load(f)
    msg = update(settings, cmd, mode)
    if msg is None:
        print("usage-statusline is not installed; nothing changed")
        return 0
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print(f"{msg} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
