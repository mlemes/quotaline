#!/usr/bin/env bash
# Install (or --uninstall) the usage status line into Claude Code settings.
# Idempotent. Backs up the settings file once, before the first change.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
settings=${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}
cmd="PYTHONPATH=$here/src python3 -m usage_statusline"
mode=${1:-install}

mkdir -p "$(dirname "$settings")"
[ -f "$settings" ] || echo '{}' >"$settings"
[ -f "$settings.bak-usage-statusline" ] || cp "$settings" "$settings.bak-usage-statusline"

python3 - "$settings" "$cmd" "$mode" <<'EOF'
import json, sys

path, cmd, mode = sys.argv[1:]
with open(path) as f:
    s = json.load(f)
current = (s.get("statusLine") or {}).get("command")
if mode == "--uninstall":
    if current == cmd:
        del s["statusLine"]
        print(f"Removed usage-statusline from {path}")
    else:
        print("usage-statusline is not installed; nothing changed")
        sys.exit(0)
else:
    if current and current != cmd:
        print(f"Replacing existing statusLine command: {current}")
    s["statusLine"] = {"type": "command", "command": cmd, "refreshInterval": 60}
    print(f"Installed usage-statusline in {path}")
with open(path, "w") as f:
    json.dump(s, f, indent=2)
    f.write("\n")
EOF
