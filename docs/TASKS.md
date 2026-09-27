# Tasks

<!-- The working memory of the project. Claude: read this before starting work,
update it as you go. Keep "Done" pruned to the last ~10 entries. -->

## Current task
(nothing in progress)

### START HERE (state as of YYYY-MM-DD, commit `<hash>`)
<!-- REQUIRED. Refresh at the end of every stage — see "Stage discipline" in
~/projects/CLAUDE.md. Written for a reader with zero chat history. -->
**Done:** <what is actually built, with test counts>
**Next:** <the exact next step, and whether any partial work exists for it>
**Verify:**
```bash
cd ~/projects/<name>
ulimit -v 400000            # runaway tests OOM-kill the terminal on this box
python3 -m pytest -q
ruff check .                # or ~/.local/bin/ruff check .
```

### Plan
<!-- For non-trivial tasks, write numbered steps here BEFORE coding.
Each step should be small enough to verify with a test run. Mark phases
DONE / ← NEXT as you go so the step list never contradicts START HERE. -->

## Up next
- [ ] Example: define the CLI interface

<!-- Record any trap discovered here (silent API caps, OOM loops, encoding traps)
so the next session does not rediscover it the hard way. -->

## Done
- [x] 2026-09-27 Project created from template
