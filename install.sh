#!/usr/bin/env bash
# Install (or --uninstall) the usage status line into Claude Code settings,
# then find agy's keyring entry for the Antigravity line (skip with --no-agy;
# pick an entry with --agy-entry N when several match).
# --dest DIR copies the code to DIR/src and runs it from there. The plugin uses its
# ${CLAUDE_PLUGIN_DATA}, which keeps its path across plugin updates. --sync only refreshes
# an existing DIR/src copy and touches no settings (the plugin's SessionStart hook).
# Idempotent. Backs up the settings file once, before the first change.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
settings=${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}
src=$here/src
dest=
mode=install
agy=yes
agy_args=()
while [ $# -gt 0 ]; do
  case $1 in
    --uninstall) mode=--uninstall ;;
    --no-agy) agy=no ;;
    --agy-entry) agy_args=(--agy-entry "${2:?--agy-entry needs a number}"); shift ;;
    --dest) dest=${2:?--dest needs a directory}; shift ;;
    --sync) mode=sync ;;
    *) echo "usage: $0 [--uninstall] [--no-agy] [--agy-entry N] [--dest DIR [--sync]]" >&2
       exit 2 ;;
  esac
  shift
done

# Swap in a fresh copy, so a running status line never sees a half-copied package.
copy_src() {
  rm -rf "$dest/src.new"
  mkdir -p "$dest/src.new"
  cp -r "$here/src/usage_statusline" "$dest/src.new/"
  rm -rf "$dest/src.new/usage_statusline/__pycache__" "$dest/src"
  mv "$dest/src.new" "$dest/src"
}

if [ "$mode" = sync ]; then
  [ -n "$dest" ] || { echo "--sync needs --dest DIR" >&2; exit 2; }
  if [ -d "$dest/src" ]; then copy_src; fi
  exit 0
fi
if [ -n "$dest" ]; then
  src=$dest/src
  if [ "$mode" = install ]; then copy_src; fi
fi
printf -v qsrc %q "$src"
cmd="PYTHONPATH=$qsrc python3 -m usage_statusline"

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

if [ "$mode" = --uninstall ] && [ -n "$dest" ]; then
  rm -rf "$dest/src"  # stops the SessionStart hook from recreating it
fi
if [ "$mode" = install ] && [ "$agy" = yes ]; then
  PYTHONPATH="$src" python3 -m usage_statusline.agy_setup "${agy_args[@]}" || true
fi
