# quotaline

This project adds quota lines to the Claude Code status line for your Claude Pro plan,
Antigravity (`agy`), and Codex CLI on your ChatGPT plan. It shows session and weekly windows
when provided, with model quota fallback for Gemini. An optional [local OmniRoute source](#use-a-local-omniroute-source-optional)
reads explicitly selected accounts instead of the native readers.

```
Claude         session  24% · resets Sun 20:00 | week  41% · resets Thu 21:13
AG Gemini      session   0% · resets Sun 16:02 | week  14% · resets Mon 23:28
AG Claude/GPT  session   0% · resets Sun 16:02 | week  19% · resets Sun 00:50
Codex          session   3% · resets Sun 19:40 | week  12% · resets Fri 08:15
```

**AG Gemini** covers Gemini models when their reported quotas match; differing model quotas
get separate rows. If Google omits the Gemini summary, its row shows `quota` with one reset
time and no weekly value. **AG Claude/GPT** covers Claude and GPT models in Antigravity. **Codex** reads the usage that Codex CLI records on your
machine (see "How it works"). Its second column reads `week` for a weekly window, or the window
length, such as `30d` on the single 30-day window of the free and Go plans.

## Use with antigravity-for-claude-code and the Codex plugin

quotaline was built to pair with two plugins that let Claude Code hand work off to another
agent:

- [antigravity-for-claude-code](https://github.com/yuting0624/antigravity-for-claude-code)
  hands work to Antigravity (`agy`).
- OpenAI's [Codex plugin for Claude Code](https://github.com/openai/codex-plugin-cc) hands
  work to Codex.

With either plugin, a single session draws on more than one quota. quotaline shows your Claude,
Antigravity, and Codex quotas side by side, which helps you see which one has room left and
decide how much work to hand off, before any of them runs out.

To install quotaline with both plugins, run:

```bash
claude plugin marketplace add yuting0624/antigravity-for-claude-code
claude plugin install antigravity@antigravity-for-claude-code
claude plugin marketplace add openai/codex-plugin-cc
claude plugin install codex@openai-codex
claude plugin marketplace add mlemes/quotaline
claude plugin install quotaline@mlemes
```

quotaline works on its own as well. It doesn't need either plugin, and it doesn't call them.

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

## Use a local OmniRoute source (optional)

Native mode remains the default. To read Claude, Antigravity and Codex subscription quotas
from an existing OmniRoute on `127.0.0.1:20128`, install with `--no-agy` if you do not need
native Antigravity setup, then:

1. In OmniRoute, supply a dedicated key with usage-command permission and an explicit
   allow-list of the connections you intend to display. An inference-capable key can still
   receive HTTP 403 for usage. quotaline does not create keys or change permissions.
2. Save that key in a private file, for example
   `~/.config/usage-statusline/omniroute-usage-key`. Use `chmod 600` on it.
3. Create `~/.config/usage-statusline/omniroute.json` using your exact connection IDs:

   ```json
   {
     "key_file": "/home/you/.config/usage-statusline/omniroute-usage-key",
     "connections": [
       {"provider": "claude", "connection_id": "your-claude-connection"},
       {"provider": "agy", "connection_id": "your-agy-connection", "alias": "work"},
       {"provider": "codex", "connection_id": "your-codex-connection"}
     ]
   }
   ```

   Keep only the connections you want, and protect this file with `chmod 600` too. Supported
   provider names are exactly `claude`, `agy`, and `codex`. An optional short printable
   `alias` appears after each label. Connection IDs select accounts; response order and the
   router's preferred account do not. No provider credentials are copied.

When this file exists, the status line uses only OmniRoute, including on errors. It does not
read Claude stdin usage, Codex transcripts or the Antigravity keyring, and does not run native
quota requests or credential recovery. Invalid config produces a visible configuration error.
Remove or rename the file to restore native mode; native configuration and caches are kept.

quotaline makes one authenticated GET to
`http://127.0.0.1:20128/api/usage/om-usage?format=json`, with a two-second timeout, no proxy
and no redirects. HTTP 401 means check the usage key; HTTP 403 means enable usage permission.
Successful and failed attempts are throttled for 60 seconds when its separate cache is writable.
This reads OmniRoute's cached subscription quotas, never its personal key budget, and makes
no inference call or provider refresh.

The header says `OmniRoute … upstream age unknown`: receipt time does not establish provider
freshness. Failed connections can retain their last complete rows with
`stale (received YYYY-MM-DD HH:MM)` alongside the error, while healthy connections update.
Past reset times do not turn historical percentages into zero. AG Gemini, AG Claude/GPT
and AG Argon update independently: absent windows display `--`; malformed or disagreeing
values, or two absent windows, fail only that row. Failed rows retain their own cached value
and receipt time with a stale marker, or show a row-specific error without history. If all
AG rows fail or the connection is unavailable, cached rows remain alongside an `AG` error.
Argon uses only its explicit weekly meter and has no session. Codex labels longer windows
by duration, such as `30d`.

The private cache is `~/.cache/usage-statusline/omniroute.json`; it stores only selected
formatted rows, opaque connection IDs, a configuration fingerprint and local timestamps.
Neither the key nor raw responses are cached. See [PRIVACY.md](PRIVACY.md) for deletion.

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

The access token expires about an hour after `agy` last refreshed it. On HTTP 401, quotaline
runs `agy models` once without a shell or interactive input, then rereads the keyring token and
retries. This lets `agy` own credential refresh without an open session. The subprocess has a
10-second limit and its process group is terminated afterward. Its output is discarded; `agy`
may write its normal logs/state, initialize its configured plugins, and make its own network
requests. No model prompt is submitted. If `agy` is missing, login was revoked, or refresh fails,
the line reports the failure. HTTP 403 does not trigger a refresh.

When a fetch fails, last successful quota rows remain visible with `stale (updated …)` and the
error. Stale values are historical, even after their reset times pass. Retries are throttled to
once per 60 seconds when the cache is writable. A cache write failure does not hide fresh usage.

## What this plugin runs, reads, writes, and sends

The native paths below apply when `omniroute.json` is absent. Configured OmniRoute mode
uses the separate local read, key file and cache described above; installers still perform
Antigravity setup unless you pass `--no-agy`.

- **Runs:** `install.sh`, only when you run `/quotaline:install` or `/quotaline:uninstall`.
  `install.sh` runs two bundled Python modules, `usage_statusline.settings_entry` (edits
  `statusLine`) and `usage_statusline.agy_setup` (finds the keyring entry). A
  SessionStart hook runs `install.sh --sync`, which copies the plugin's Python code into its data
  directory, and only if you already installed. The status line runs
  `python3 -m usage_statusline` from that copy. Nothing is downloaded or installed from a
  package registry. On HTTP 401, it also runs bounded `agy models` as described above.
- **Reads:** the status line JSON that Claude Code sends (for `rate_limits`). During setup, the
  labels and attributes of your keyring entries (through `gdbus`) and the one matching `agy`
  entry (through `secret-tool`). At run time, the saved `secret-tool lookup` command, which
  returns `agy`'s current OAuth access token. The plugin never prints or stores the token. Also
  the last 256 KiB of up to 3 of the newest Codex session files under `~/.codex/sessions` (or
  `$CODEX_HOME/sessions`). It uses only the `rate_limits` field of the last `token_count`
  event. It never reads `~/.codex/auth.json`.
- **Writes:** the `statusLine` key in `~/.claude/settings.json`, with a one-time backup,
  `~/.config/usage-statusline/agy_token_cmd` (the lookup command, not the token),
  `~/.cache/usage-statusline/antigravity.json` (formatted lines, successful rows and timestamps),
  temporary files beside that cache for atomic replacement, and the code copy in the
  plugin's data directory.
- **Sends:** quota requests during Antigravity setup and then at most one fetch cycle every
  60 seconds when the cache is writable. A cycle calls
  `https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary` and, when
  Gemini is absent, `v1internal:fetchAvailableModels` on the same host. Both use `POST`, body
  `{}`, `User-Agent: antigravity/cli/1.4.2`, and the `agy` Google access token as a Bearer token.
  This header exposes the Gemini session/week and separate Argon weekly groups; the bare
  `antigravity` header can omit both. An HTTP 401 can trigger one `agy models` refresh and one
  retry of the failed request. These
  internal APIs can change without notice. Without a token command, no requests or refresh
  subprocesses run. quotaline has no telemetry; `agy` retains its own network/state behavior.

## Notes for reviewers

The plugin directory's checks flag the points below. Each one is deliberate, and this section
says why. The code lives in `src/usage_statusline/`, and every file is short enough to read in
full.

### The `agy` token goes to `daily-cloudcode-pa.googleapis.com`

Checks: `MCP_FORWARDS_CREDENTIAL_ENV` on `README.md` and `antigravity.py`.

- **What the credential is.** The OAuth access token that the Antigravity CLI (`agy`) keeps in
  the system keyring (`service=gemini`, `username=antigravity`). Google issues it.
- **Where it goes.** Only to `daily-cloudcode-pa.googleapis.com`, Google's Cloud Code API. The
  host serves the quota endpoints that `agy` also uses. `antigravity.fetch_line` builds
  these requests. The plugin itself never sends refresh credentials; `agy` owns refresh.
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

`antigravity.py` starts the saved token command without a shell (`shlex.split`, `shell=False`).
On HTTP 401 it can also run the installed `agy models` command once, with no stdin, discarded
output, a 10-second timeout, and process-group cleanup. It rereads the token after successful
refresh. This delegates credential handling to `agy`; quotaline does not implement OAuth or
write the keyring. API responses are parsed with `json.load` into percentages and times;
nothing from them is run or written as code.

### The SessionStart hook passes `${CLAUDE_PLUGIN_DATA}`

The status line must keep one path in `~/.claude/settings.json`, but `${CLAUDE_PLUGIN_ROOT}`
changes on every plugin update. The hook copies the plugin's own `src/usage_statusline/` into
`${CLAUDE_PLUGIN_DATA}/src`, and only if you've already installed. It changes no settings
and makes no network requests.

## How it works

These are the default native readers; optional OmniRoute mode replaces this runtime path.

- The Claude line reads `rate_limits.five_hour` and `rate_limits.seven_day` from the JSON that
  Claude Code sends to the status line. Claude Code provides these fields only for Pro and Max
  plans, and only after the first API response in a session.
- The Antigravity lines call the `v1internal:retrieveUserQuotaSummary` endpoint that `agy` uses.
  It supplies explicit 5-hour and weekly buckets. Some accounts now omit Gemini, so the line
  supplements it with `v1internal:fetchAvailableModels`. Identical Gemini quota/reset pairs
  share a row; differing quotas keep their model labels. Model-level data is labeled `quota`,
  without inventing a weekly window. Missing model fractions remain unknown. Requests and
  token lookups have a 2-second timeout each; credential recovery additionally allows up to
  10 seconds for `agy models`. The cache preserves successful rows during partial failures,
  marks historical rows stale, and throttles retries for 60 seconds. Cache files from 0.2.0
  remain readable.
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
