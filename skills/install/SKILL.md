---
name: install
description: Install the usage status line, which shows Claude Pro, Antigravity, and Codex session and weekly quota usage, in your Claude Code settings.
disable-model-invocation: true
argument-hint: "[--no-agy] [--agy-entry N]"
---

Run this command with the Bash tool, then show the user its output:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/install.sh" --dest "${CLAUDE_PLUGIN_DATA}" $ARGUMENTS
```

The command sets `statusLine` in `~/.claude/settings.json` and backs the file up once, to
`settings.json.bak-usage-statusline`. It then looks for the Antigravity (`agy`) token in the
system keyring. It never prints the token, and you must never print it either.

After it runs, tell the user:

- Restart Claude Code. The Claude line fills in after the first reply.
- If the output lists several keyring entries, run `/quotaline:install --agy-entry N`.
- If it asks for `secret-tool`, run `sudo apt install libsecret-tools`, then install again.
- To skip Antigravity, run `/quotaline:install --no-agy`.
