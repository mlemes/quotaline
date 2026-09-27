# Tasks

## Current task
(nothing in progress)

### START HERE (state as of 2026-09-27, stage commit follows `fbcd196`)
**Done:** The Claude line, the Antigravity lines (one per quota group, from
`retrieveUserQuotaSummary`), `install.sh`, and the keyring auto-setup (`agy_setup.py`) are
built. The project is also a Claude Code plugin and its own marketplace, `usage-statusline@mlemes`,
published at https://github.com/mlemes/usage-statusline. All 35 tests pass, lint is clean, and
`claude plugin validate .` passes with one expected warning (no `version`). All lines share one
aligned layout from `claude.py`. On 2026-09-27, the Antigravity lines were verified live:

```
AG Gemini      session   0% · resets Sun 16:02 | week  14% · resets Mon 23:28
AG Claude/GPT  session   0% · resets Sun 16:02 | week  19% · resets Sun 00:50
```

The maintainer's machine still runs the status line from this checkout (installed with `./install.sh`
on 2026-09-27, backup at `~/.claude/settings.json.bak-usage-statusline`). The plugin install
path (`/usage-statusline:install`) was not yet run end to end.

**Next:**
1. Install from the public marketplace (`claude plugin marketplace add mlemes/usage-statusline`,
   `claude plugin install usage-statusline@mlemes`), run `/usage-statusline:install`, restart,
   and confirm all three lines show.

**Verify:**
```bash
cd ~/Projects/projects/usage-statusline
~/.local/bin/uvx --with pytest pytest -q     # no pip for python3 on this box
~/.local/bin/uvx ruff check .
echo '{}' | PYTHONPATH=src python3 -m usage_statusline
claude plugin validate .
```

### Plan
1. DONE: `claude.py` formats the 5-hour and 7-day windows from the status line JSON.
2. DONE: `antigravity.py` handles the token command, API call, parsing, and 60-second cache.
3. DONE: `main.py` prints both lines.
4. DONE: `install.sh` handles install and uninstall, idempotent, with a one-time backup.
5. DONE: Docs.
6. DONE: `agy_setup.py` plus `install.sh` flags `--no-agy` and `--agy-entry N`.
7. DONE: Run live verification of both lines (see **Next** in START HERE).
8. DONE: One aligned Antigravity line per quota group with session and weekly windows.
9. DONE: Plugin and `mlemes` marketplace, published to the public repository.

## Up next
(nothing)

## Traps
- A plugin can't set `statusLine`. Only the install skill can, through `install.sh`.
- Don't point `statusLine` at `${CLAUDE_PLUGIN_ROOT}`. It changes on every plugin update.
- `${CLAUDE_PLUGIN_DATA}` isn't set in the Bash tool's environment. Skills must write the
  `${...}` reference in the Markdown body, where Claude Code substitutes it.
- Any test that runs the status line command must set a temp `HOME` and
  `USAGE_STATUSLINE_AGY_TOKEN_CMD=true`, or it reads the real keyring and cache.
- Claude Code's auto-mode safety check blocks keyring exploration (`gdbus` or `secret-tool`
  on `org.freedesktop.secrets`) and even edits that wire it into `install.sh`, despite your
  approval in chat. Do that work in default permission mode, and have the user run the real
  keyring step.
- The Code Assist API returns 403 for the default `Python-urllib` User-Agent. Keep
  `User-Agent: antigravity`.
- `retrieveUserQuotaSummary` returns 400 if the body has a `metadata` field. Send `{}`.
- `fetchAvailableModels` has no weekly window and hides that Flash and Pro share a quota. Do not
  go back to it.
- agy nests the oauth2 token under `"token"` in its keyring secret.
- Tests must pass `--no-agy` to `install.sh`, or they touch the real keyring.
- `python3 -m pytest` fails with `No module named pytest`. Use `uvx --with pytest`.
- `git mv -k` on an untracked directory silently does nothing. Use plain `mv`.

## Done
- [x] 2026-09-27 Plugin, `mlemes` marketplace, MIT license, and public repo (35 tests).
- [x] 2026-09-27 One aligned line per Antigravity quota group, session and weekly (31 tests).
- [x] 2026-09-27 Antigravity line verified live (fixed the nested token and the User-Agent 403).
- [x] 2026-09-27 `install.sh` auto-finds the agy keyring entry (27 tests, fake keyring only).
- [x] 2026-09-27 Ran `install.sh` against the real Claude settings (`79c003f`).
- [x] 2026-09-27 Built the Claude line, Antigravity line, and installer (15 tests).
- [x] 2026-09-27 Project created from template (`7cc1598`).
