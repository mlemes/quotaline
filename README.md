# usage-statusline

This project adds three aligned lines to the Claude Code status line. They show the 5-hour
session and weekly usage, each with its reset time, for your Claude Pro plan and for each
Antigravity (`agy`) quota group.

```
Claude         session  24% · resets Sun 20:00 | week  41% · resets Thu 21:13
AG Gemini      session   0% · resets Sun 16:02 | week  14% · resets Mon 23:28
AG Claude/GPT  session   0% · resets Sun 16:02 | week  19% · resets Sun 00:50
```

**AG Gemini** covers Gemini Flash and Pro, which share one quota. **AG Claude/GPT** covers the
Claude and GPT models in Antigravity.

## Install

1. Run the installer:

   ```bash
   ./install.sh
   ```

   The installer adds a `statusLine` entry to `~/.claude/settings.json`. Before its first
   change, it saves a backup to `~/.claude/settings.json.bak-usage-statusline`. It then sets
   up the Antigravity line (see the next section). You can run it again safely.
2. Restart Claude Code, or send a message. The Claude line fills in after the first reply.

To remove the status line, run `./install.sh --uninstall`. To skip the Antigravity setup, run
`./install.sh --no-agy`.

## Set up the Antigravity line

`agy` keeps its OAuth access token in the system keyring. The installer runs
`python3 -m usage_statusline.agy_setup`, which does the following:

1. Lists keyring entry labels and attributes through `gdbus`. It skips the Antigravity IDE's
   **Antigravity Safe Storage** entry.
2. Picks the entry that mentions `antigravity`, `jetski`, or `agy`. If several match, it lists
   them and stops, and you rerun with `./install.sh --agy-entry N`.
3. Reads that entry once to check that it holds a token. It never prints the token.
4. Saves `secret-tool lookup <attributes>` to `~/.config/usage-statusline/agy_token_cmd`.
5. Prints the resulting Antigravity line.

The setup needs `secret-tool`. If it's missing, the installer tells you to run
`sudo apt install libsecret-tools`. To set the command by hand instead, write it to
`~/.config/usage-statusline/agy_token_cmd`, or export it as `USAGE_STATUSLINE_AGY_TOKEN_CMD`.
The status line accepts a plain token, oauth2 JSON with `access_token`, or a
`go-keyring-base64:` value.

The access token expires about an hour after `agy` last refreshed it. When it expires, the line
shows `n/a (HTTP 401, run agy to refresh login)` until you use `agy` again.

## How it works

- The Claude line reads `rate_limits.five_hour` and `rate_limits.seven_day` from the JSON that
  Claude Code sends to the status line. Claude Code provides these fields only for Pro and Max
  plans, and only after the first API response in a session.
- The Antigravity lines call the `v1internal:retrieveUserQuotaSummary` endpoint that `agy` uses.
  It returns one quota group per model family, each with a 5-hour and a weekly bucket. The
  result, including errors, is cached in `~/.cache/usage-statusline/antigravity.json` for 60
  seconds, with a 2-second timeout.
- A missing window shows `--` and keeps its width, so the columns stay aligned.
