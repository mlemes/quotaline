---
name: uninstall
description: Remove the usage status line from your Claude Code settings.
disable-model-invocation: true
---

Run this command with the Bash tool, then show the user its output:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/install.sh" --dest "${CLAUDE_PLUGIN_DATA}" --uninstall
```

The command removes `statusLine` from `~/.claude/settings.json` only if it still points at this
plugin. Tell the user to restart Claude Code, and that they can now uninstall the plugin with
`claude plugin uninstall usage-statusline@mlemes`.
