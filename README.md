# usage-statusline

This project adds two lines to the Claude Code status line. They show your Claude Pro session
and weekly usage, and your Antigravity (`agy`) quota, each with its reset time.

```
Claude       session 24% · resets Sun 20:00 | week 41% · resets Thu 21:13
Antigravity  Flash 25% · resets Sun 15:00 | Pro 3% · resets Mon 01:00
```

## Install

1. Run the installer:

   ```bash
   ./install.sh
   ```

   The installer adds a `statusLine` entry to `~/.claude/settings.json`. Before its first
   change, it saves a backup to `~/.claude/settings.json.bak-usage-statusline`. You can run it
   again safely.
2. Restart Claude Code, or send a message. The Claude line fills in after the first reply.

To remove the status line, run `./install.sh --uninstall`.

## Set up the Antigravity line

`agy` keeps its OAuth access token in the system keyring. The status line runs a command that
you choose to print that token. It never searches the keyring by itself.

1. Find the `agy` entry in your keyring. You can use **Passwords and Keys** (Seahorse), or run
   `secret-tool search --all service <name>` if you install `libsecret-tools`.
2. Write a command that prints only the access token. If the stored secret is JSON, pipe it
   through `jq -r .access_token`.
3. Save the command to `~/.config/usage-statusline/agy_token_cmd`, or export it as
   `USAGE_STATUSLINE_AGY_TOKEN_CMD`.

The access token expires about an hour after `agy` last refreshed it. When it expires, the line
shows `n/a (HTTP 401, run agy to refresh login)` until you use `agy` again.

## How it works

- The Claude line reads `rate_limits.five_hour` and `rate_limits.seven_day` from the JSON that
  Claude Code sends to the status line. Claude Code provides these fields only for Pro and Max
  plans, and only after the first API response in a session.
- The Antigravity line calls the `v1internal:fetchAvailableModels` endpoint that `agy` uses. It
  caches the result, including errors, in `~/.cache/usage-statusline/antigravity.json` for 60
  seconds, with a 2-second timeout.
