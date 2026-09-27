---
name: verify
description: Run the full verification loop (lint, format, tests) and fix anything that fails. Use before declaring any task done or committing.
---

# Verify

Run these steps in order. Do not skip steps. Do not stop until all pass or you are blocked.

1. `ruff check --fix .` — if errors remain that autofix can't solve, fix them by hand and re-run.
2. `ruff format .`
3. `python3 -m pytest -q` — if a test fails:
   - Read the failing test and the code it tests before changing anything.
   - Fix the root cause. Never delete, skip, or weaken a test to make it pass.
   - Re-run until green.
4. Report the final pytest output (the summary line) to the user.

If you cannot make everything pass, say exactly which step fails, show the error, and explain what is blocking — do not claim partial success as done.
