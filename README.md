# quotaline

This project adds four aligned lines to the Claude Code status line. They show the 5-hour
session and weekly usage, each with its reset time, for your Claude Pro plan, for each
Antigravity (`agy`) quota group, and for Codex CLI on your ChatGPT plan.

```
Claude         session  24% · resets Sun 20:00 | week  41% · resets Thu 21:13
AG Gemini      session   0% · resets Sun 16:02 | week  14% · resets Mon 23:28
AG Claude/GPT  session   0% · resets Sun 16:02 | week  19% · resets Sun 00:50
Codex          session   3% · resets Sun 19:40 | week  12% · resets Fri 08:15
```

**AG Gemini** covers Gemini Flash and Pro, which share one quota. **AG Claude/GPT** covers the
Claude and GPT models in Antigravity. **Codex** reads the usage that Codex CLI records on your
machine (see "How it works"). Its second column reads `week` for a weekly window, or the window
length, such as `30d` on the single 30-day window of the free and Go plans.

quotaline also pairs well with OpenAI's `codex` plugin for Claude Code, which hands work to
Codex. quotaline shows how much Codex quota is left. It doesn't need that plugin and doesn't
call it.

## Use with antigravity-for-claude-code

quotaline was built to pair with the
[antigravity-for-claude-code](https://github.com/yuting0624/antigravity-for-claude-code)
plugin. That plugin lets Claude Code hand work off to Antigravity (`agy`), so a single session
draws on both your Claude and your Antigravity quotas. quotaline shows both quotas side by side,
which helps you see which one has room left and decide how much work to hand off, before either
one runs out.

To install both plugins, run:

```bash
claude plugin marketplace add yuting0624/antigravity-for-claude-code
claude plugin install antigravity@antigravity-for-claude-code
claude plugin marketplace add mlemes/quotaline
claude plugin install quotaline@mlemes
```

quotaline works on its own as well. It doesn't need the other plugin, and it doesn't call it.

## Requirements

- Linux with `python3` 3.13 or later. The Antigravity setup also needs `gdbus` and
  `secret-tool` (`sudo apt install libsecret-tools`).
- A Claude Pro or Max plan for the Claude line, and a logged-in `agy` for the Antigravity lines.
- Optional: Codex CLI, used at least once on this machine, for the Codex line. It needs no setup.

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
5. Fetches the Antigravity quota from Google once and prints the resulting line.

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

- **Runs:** `install.sh`, only when you run `/quotaline:install` or `/quotaline:uninstall`.
  `install.sh` runs two bundled Python modules, `usage_statusline.settings_entry` (edits
  `statusLine`) and `usage_statusline.agy_setup` (finds the keyring entry). A
  SessionStart hook runs `install.sh --sync`, which copies the plugin's Python code into its data
  directory, and only if you already installed. The status line runs
  `python3 -m usage_statusline` from that copy. Nothing is downloaded or installed from a
  package registry.
- **Reads:** the status line JSON that Claude Code sends (for `rate_limits`). During setup, the
  labels and attributes of your keyring entries (through `gdbus`) and the one matching `agy`
  entry (through `secret-tool`). At run time, the saved `secret-tool lookup` command, which
  returns `agy`'s current OAuth access token. The plugin never prints or stores the token. Also
  the last 256 KiB of up to 3 of the newest Codex session files under `~/.codex/sessions` (or
  `$CODEX_HOME/sessions`). It uses only the `rate_limits` field of the last `token_count`
  event. It never reads `~/.codex/auth.json`.
- **Writes:** the `statusLine` key in `~/.claude/settings.json`, with a one-time backup,
  `~/.config/usage-statusline/agy_token_cmd` (the lookup command, not the token),
  `~/.cache/usage-statusline/antigravity.json` (the formatted lines), and the code copy in the
  plugin's data directory.
- **Sends:** one HTTPS request when `/quotaline:install` finishes the Antigravity setup, to
  show the line, and then at most one every 60 seconds from the status line. Each is a `POST`
  with body `{}` to
  `https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary`, with the
  `agy` token as a Bearer token. The token is a Google OAuth token that Google issued to
  `agy`, and it goes only to Google's own API, the endpoint that `agy` itself calls. It's
  internal and undocumented, so it can change without notice. Without the Antigravity setup,
  the plugin makes no network requests. There's no telemetry, and nothing else leaves your
  machine.

## Notes for reviewers

The plugin directory's checks flag the points below. Each one is deliberate, and this section
says why. The code lives in `src/usage_statusline/`, and every file is short enough to read in
full.

### The `agy` token goes to `daily-cloudcode-pa.googleapis.com`

Checks: `MCP_FORWARDS_CREDENTIAL_ENV` on `README.md` and `antigravity.py`.

- **What the credential is.** The OAuth access token that the Antigravity CLI (`agy`) keeps in
  the system keyring (`service=gemini`, `username=antigravity`). Google issues it.
- **Where it goes.** Only to `daily-cloudcode-pa.googleapis.com`, Google's Cloud Code API. The
  host is the token's own issuer and audience, and it's the same endpoint `agy` calls for the
  same data. `antigravity.fetch_line` builds the only request in the plugin.
- **Why not `user_config`.** The access token expires about one hour after `agy` refreshes it,
  and only `agy` holds the refresh credentials. A value you paste once would stop working
  within the hour. Reading the current token from the keyring at run time is the only way the
  line stays current without the plugin handling refresh tokens itself.
- **What the plugin keeps.** It saves the lookup command (`secret-tool lookup service gemini
  username antigravity`), never the token. It never prints, logs, or caches the token. The
  cache holds only the formatted percentages and reset times.
- **`USAGE_STATUSLINE_AGY_TOKEN_CMD`.** An optional override for that saved command. Its value
  is a command, not a token, and the status line runs it without a shell.
- **When it happens.** Once when you run `/quotaline:install`, which the model can't invoke on
  its own (`disable-model-invocation: true`), and then from the status line. `/quotaline:install --no-agy` skips the keyring
  and the network entirely.

### `install.sh` runs bundled Python

Check: `COMMAND_SCRIPT_NOT_FOLLOWED`.

`install.sh` runs `python3 -m usage_statusline.settings_entry` and
`python3 -m usage_statusline.agy_setup`, both shipped in `src/usage_statusline/`. Editing
`~/.claude/settings.json` needs a JSON parser, and Python's standard library is safer than
`sed` or `jq`. The script has no here-documents, package launchers, package installs, or
downloads, and the Python code uses only the standard library.

### A URL fetch next to a process start

Check: `RUNTIME_FETCH_EXEC` on `antigravity.py`.

The only process `antigravity.py` starts is the saved token command, which runs before the
request, without a shell (`shlex.split`, `shell=False`). The response is parsed with
`json.load` into percentages and times, and nothing from it is run or written as code.

### The SessionStart hook passes `${CLAUDE_PLUGIN_DATA}`

The status line must keep one path in `~/.claude/settings.json`, but `${CLAUDE_PLUGIN_ROOT}`
changes on every plugin update. The hook copies the plugin's own `src/usage_statusline/` into
`${CLAUDE_PLUGIN_DATA}/src`, and only if you've already installed. It changes no settings
and makes no network requests.

## How it works

- The Claude line reads `rate_limits.five_hour` and `rate_limits.seven_day` from the JSON that
  Claude Code sends to the status line. Claude Code provides these fields only for Pro and Max
  plans, and only after the first API response in a session.
- The Antigravity lines call the `v1internal:retrieveUserQuotaSummary` endpoint that `agy` uses.
  It returns one quota group per model family, each with a 5-hour and a weekly bucket. The
  result, including errors, is cached in `~/.cache/usage-statusline/antigravity.json` for 60
  seconds, with a 2-second timeout.
- The Codex line reads the session transcripts that Codex CLI writes, at
  `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`. It makes no network request and writes no
  cache. The numbers are as fresh as your last Codex response on this machine. Usage from Codex
  on other machines or ChatGPT on the web appears after your next Codex run here. If a window's
  reset time has passed, the line shows `0%` and `--` for the reset, because the window reset
  since Codex last ran. If `~/.codex/sessions` doesn't exist, there is no Codex line. If it
  exists but holds no usage event yet, the line reads `Codex          no usage yet`. Codex's
  transcript format is internal and undocumented, so it can change between Codex versions. It
  was verified on Codex CLI 0.158.0.
- A missing window shows `--` and keeps its width, so the columns stay aligned.

## Privacy

quotaline sends no data to its author and has no telemetry. [PRIVACY.md](PRIVACY.md) lists what it
reads, stores, and sends, and how to delete it.

## License

MIT. See `LICENSE`.
