# Tasks

## Current task
(nothing in progress)

### START HERE (state as of 2026-09-27, stage commit follows scaffold `7cc1598`)
**Done:** The Claude line, the Antigravity line (parser, cache, and token command), and
`install.sh` are built. All 15 tests pass and lint is clean. `install.sh` has NOT been run
against the real `~/.claude/settings.json` yet.

**Next:**
1. Run `./install.sh` and confirm that the Claude line shows real numbers after one reply.
2. Configure the `agy` token command (see `README.md`), then confirm that the live
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
6. NEXT: Run live verification of both lines (see **Next** in START HERE).

## Up next
- [ ] Verify the Antigravity response shape against a live call.
- [ ] Decide whether the Antigravity line should show weekly caps separately, if the API
      exposes them. Right now it shows one reset time per model family.

## Traps
- Claude Code's auto-mode safety check blocks keyring exploration (`gdbus` or `secret-tool`
  on `org.freedesktop.secrets`), even with your approval in chat. The token command is
  therefore set up by you and never discovered by the script.
- `python3 -m pytest` fails with `No module named pytest`. Use `uvx --with pytest`.
- `git mv -k` on an untracked directory silently does nothing. Use plain `mv`.

## Done
- [x] 2026-09-27 Built the Claude line, Antigravity line, and installer (15 tests).
- [x] 2026-09-27 Project created from template (`7cc1598`).
