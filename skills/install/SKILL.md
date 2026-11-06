---
name: install
description: Install the usage status line, which shows Claude Pro, Antigravity, and Codex session and weekly quota usage, in your Claude Code settings.
disable-model-invocation: true
argument-hint: "[--no-agy] [--agy-entry N] [--sync]"
---

Run this command with the Bash tool, then show the user its output:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/install.sh" --dest "${CLAUDE_PLUGIN_DATA}" $ARGUMENTS
```

With `--sync`, the command only refreshes an existing installed code copy. It changes no
settings, skips keyring setup, and does nothing if the status line isn't installed. Run
`/quotaline:install --sync` after each plugin update; the plugin has no automatic sync hook.

Without `--sync`, the command sets `statusLine` in `~/.claude/settings.json` and backs the file up once, to
`settings.json.bak-usage-statusline`. It then looks for the Antigravity (`agy`) token in the
system keyring. It never prints the token, and you must never print it either.

After a regular install, tell the user:

- Restart Claude Code. The Claude line fills in after the first reply.
- If the output lists several keyring entries, run `/quotaline:install --agy-entry N`.
- If it asks for `secret-tool`, run `sudo apt install libsecret-tools`, then install again.
- To skip Antigravity, run `/quotaline:install --no-agy`.
