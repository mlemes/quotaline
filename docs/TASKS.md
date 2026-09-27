# Tasks

## Current task
(nothing in progress)

### START HERE (state as of 2026-09-27, stage commit follows scaffold `7cc1598`)
**Done:** The Claude line, the Antigravity line (parser, cache, and token decoding), `install.sh`,
and the keyring auto-setup (`agy_setup.py`, run by `install.sh`) are built. All 27 tests pass
and lint is clean. On 2026-09-27, `install.sh` was run
against the real `~/.claude/settings.json` (before `agy_setup` existed). No `statusLine`
existed before. The backup is at `~/.claude/settings.json.bak-usage-statusline`.
`agy_setup` has NOT been run on the real keyring. You must run it, because Claude Code's auto
mode blocks keyring access.

**Next:**
1. Restart Claude Code and confirm that the Claude line shows real numbers after one reply.
2. Run `./install.sh` again to run `agy_setup`. If it lists several entries, rerun with
   `--agy-entry N`. Then confirm that the live
   `fetchAvailableModels` response matches `docs/DATA.md`. If it doesn't, fix
   `antigravity.parse_quota` and its fixture in `tests/test_antigravity.py`.

**Verify:**
```bash
cd ~/Projects/projects/usage-statusline
~/.local/bin/uvx --with pytest pytest -q     # no pip for python3 on this box
~/.local/bin/uvx ruff check .
echo '{}' | PYTHONPATH=src python3 -m usage_statusline
```

### Plan
1. DONE: `claude.py` formats the 5-hour and 7-day windows from the status line JSON.
2. DONE: `antigravity.py` handles the token command, API call, parsing, and 60-second cache.
3. DONE: `main.py` prints both lines.
4. DONE: `install.sh` handles install and uninstall, idempotent, with a one-time backup.
5. DONE: Docs.
6. DONE: `agy_setup.py` plus `install.sh` flags `--no-agy` and `--agy-entry N`.
7. NEXT: Run live verification of both lines (see **Next** in START HERE).

## Up next
- [ ] Verify the Antigravity response shape against a live call.
- [ ] Decide whether the Antigravity line should show weekly caps separately, if the API
      exposes them. Right now it shows one reset time per model family.

## Traps
- Claude Code's auto-mode safety check blocks keyring exploration (`gdbus` or `secret-tool`
  on `org.freedesktop.secrets`) and even edits that wire it into `install.sh`, despite your
  approval in chat. Do that work in default permission mode, and have the user run the real
  keyring step.
- Tests must pass `--no-agy` to `install.sh`, or they touch the real keyring.
- `python3 -m pytest` fails with `No module named pytest`. Use `uvx --with pytest`.
- `git mv -k` on an untracked directory silently does nothing. Use plain `mv`.

## Done
- [x] 2026-09-27 `install.sh` auto-finds the agy keyring entry (27 tests, fake keyring only).
- [x] 2026-09-27 Ran `install.sh` against the real Claude settings (`79c003f`).
- [x] 2026-09-27 Built the Claude line, Antigravity line, and installer (15 tests).
- [x] 2026-09-27 Project created from template (`7cc1598`).
