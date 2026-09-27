# usage-statusline

Claude Code status line that shows Claude Pro and Antigravity quota usage with reset times, plus an install script.

## Commands
- Test: `python3 -m pytest -q` (no pip on this box: `~/.local/bin/uvx --with pytest==9.1.1 pytest -q`)
- Lint + format: `ruff check --fix . && ruff format .` (or `~/.local/bin/uvx ruff==0.16.9 ...`)
- Run: `PYTHONPATH=src python3 -m usage_statusline`  <!-- src-layout: the package is not on sys.path without this -->
  (pytest does not need it — `[tool.pytest.ini_options] pythonpath = ["src"]` covers the test run only)

## Definition of done
A change is done only when ALL of these are true:
1. `python3 -m pytest -q` passes (show the output)
2. `ruff check .` reports no errors
3. New behavior has at least one test in `tests/`
4. **The docs are updated to match** — see "Stage discipline" in `~/projects/CLAUDE.md`:
   `docs/TASKS.md` START HERE block (done / next step / commit hash), the
   `docs/ARCHITECTURE.md` module Status column and any new decision, and
   `docs/DATA.md` if a schema, dataset, or measured figure changed.
   Assume the next session starts with zero chat history.
5. The change is committed with a descriptive one-line message

## Where things go
- Code: `src/usage_statusline/`
- Tests: `tests/test_<module>.py` — mirror the module they test
- Data files: `data/raw/` (immutable inputs) and `data/processed/` (outputs) — both gitignored
- Data schemas: `docs/DATA.md` — the source of truth about datasets; keep it current with /explore-data
- Pipeline steps: `pipelines/NN_name.py` — numbered, each independently re-runnable
- Exploration scripts: `explore/` — throwaway analysis; conclusions go into `docs/DATA.md`, not here
- Architecture notes and decisions: `docs/ARCHITECTURE.md` — update it when you add a module or change how modules interact
- Current work: `docs/TASKS.md` — check the current task before starting; mark items done when finished

## Data rules
- NEVER read a whole data file into context — max 50 rows (`LIMIT 50`, `head -50`). Work from `docs/DATA.md` instead.
- Prefer DuckDB SQL for filtering/joins/aggregation (streams from disk); use pandas only on small, already-reduced data. This device has ~1GB RAM.
- `data/raw/` is immutable: transforms read from it and write to `data/processed/`, never modify it.

## Rules
- Follow the workspace rules in `~/projects/CLAUDE.md`.
- Standard library first; ask before adding any dependency.
- Type hints on all public functions.
