# quotaline

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

## Requirements

- Linux with `python3` 3.13 or later. The Antigravity setup also needs `gdbus` and
  `secret-tool` (`sudo apt install libsecret-tools`).
- A Claude Pro or Max plan for the Claude line, and a logged-in `agy` for the Antigravity lines.

## Install as a Claude Code plugin

1. Add the marketplace and install the plugin:

   ```bash
   claude plugin marketplace add mlemes/quotaline
   claude plugin install quotaline@mlemes
   ```

2. In a Claude Code session, run `/quotaline:install`. It copies the code to the
   plugin's data directory, adds a `statusLine` entry to `~/.claude/settings.json`, and sets up
   the Antigravity line. Pass `--no-agy` or `--agy-entry N` as with `install.sh`.
3. Restart Claude Code. The Claude line fills in after the first reply.

A plugin can't set your status line by itself, so step 2 is required. After a plugin update,
the plugin refreshes its copy of the code at the next session start. To remove the status line,
run `/quotaline:uninstall`, then `claude plugin uninstall quotaline@mlemes`.

## Install from a clone

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
The status line runs the code from your clone, so keep the clone in place.

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
The status line runs it as one program with arguments, without a shell, so pipes and `$VARS`
don't work. Wrap anything more complex in a script and save the script's path.
The status line accepts a plain token, oauth2 JSON with `access_token`, or a
`go-keyring-base64:` value.

The access token expires about an hour after `agy` last refreshed it. When it expires, the line
shows `n/a (HTTP 401, run agy to refresh login)` until you use `agy` again.

## What this plugin runs, reads, and sends

- **Runs:** `install.sh`, only when you run `/quotaline:install` or `/quotaline:uninstall`. A
  SessionStart hook runs `install.sh --sync`, which copies the plugin's Python code into its data
  directory, and only if you already installed. The status line runs
  `python3 -m usage_statusline` from that copy. Nothing is downloaded or installed from a
  package registry.
- **Reads:** the status line JSON that Claude Code sends (for `rate_limits`). During setup, the
  labels and attributes of your keyring entries (through `gdbus`) and the one matching `agy`
  entry (through `secret-tool`). At run time, the saved `secret-tool lookup` command, which
  returns `agy`'s current OAuth access token. The plugin never prints or stores the token.
- **Writes:** the `statusLine` key in `~/.claude/settings.json`, with a one-time backup,
  `~/.config/usage-statusline/agy_token_cmd` (the lookup command, not the token),
  `~/.cache/usage-statusline/antigravity.json` (the formatted lines), and the code copy in the
  plugin's data directory.
- **Sends:** at most one HTTPS request every 60 seconds, a `POST` with body `{}` to
  `https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary`, with the
  `agy` token as a Bearer token. The token is a Google OAuth token that Google issued to `agy`,
and it goes only to Google's own API, the endpoint that `agy` itself calls. It's
  internal and undocumented, so it can change without notice. Without the Antigravity setup,
  the plugin makes no network requests. There's no telemetry, and nothing else leaves your
  machine.

## How it works

- The Claude line reads `rate_limits.five_hour` and `rate_limits.seven_day` from the JSON that
  Claude Code sends to the status line. Claude Code provides these fields only for Pro and Max
  plans, and only after the first API response in a session.
- The Antigravity lines call the `v1internal:retrieveUserQuotaSummary` endpoint that `agy` uses.
  It returns one quota group per model family, each with a 5-hour and a weekly bucket. The
  result, including errors, is cached in `~/.cache/usage-statusline/antigravity.json` for 60
  seconds, with a 2-second timeout.
- A missing window shows `--` and keeps its width, so the columns stay aligned.

## License

MIT. See `LICENSE`.
