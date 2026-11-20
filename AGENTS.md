# AGENTS.md

Quotaline (`usage-statusline`) is a Claude Code status line that renders Claude Pro,
Antigravity (`agy`), Codex CLI, and optional local OmniRoute or OpenCode Go quota usage.
It is a standard-library Python package under [`src/usage_statusline/`](src/usage_statusline/),
installed by [`install.sh`](install.sh) or the plugin skills. See [`README.md`](README.md) for
behavior and setup, [`PRIVACY.md`](PRIVACY.md) for data handling, and
[`docs/architecture.md`](docs/architecture.md) / [`docs/DATA.md`](docs/DATA.md) for design and
source semantics.

## Environment and checks

Requires Python 3.13 or later, as declared in [`pyproject.toml`](pyproject.toml). Runtime code
uses the standard library. Install pytest and Ruff in a local virtual environment.

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install pytest ruff
```

For an Antigravity change, run the provider tests and lint its source and tests.

```bash
python3 -m pytest tests/test_antigravity.py
python3 -m ruff check src/usage_statusline/antigravity.py tests/test_antigravity.py
```

Use the corresponding files for another provider. Before handing off, run the full suite and lint.

```bash
python3 -m pytest
python3 -m ruff check .
```

## Quotaline-specific rules

1. **Protect credentials and session data.** Never print, log, commit, paste into an issue, or
   add as a fixture any real token, API key, `auth.json`, OmniRoute key, provider response, or
   Codex transcript. Isolate the home directory, keyring and caches during tests. Tokens and
   provider data can identify accounts, and transcripts contain prompts and replies.
2. **Use synthetic, offline fixtures for status-line changes.** Add or update deterministic
   fixtures and mocks (for example [`tests/fixtures/omniroute.json`](tests/fixtures/omniroute.json)
   and the monkeypatched readers in [`tests/`](tests/)). Cover the relevant known, missing,
   malformed, stale or hidden states at the affected entry point. Offline tests make the
   output reproducible without using real accounts.
3. **Keep true zero separate from missing or unknown.** Preserve a reported zero. Represent
   unavailable data with the provider’s existing markers or omitted rows. Keep usage and
   reset availability distinct so a missing reset never becomes a fabricated timestamp or
   percentage. Historical values stay historical.
4. **Preserve provider-specific reset semantics.** Codex displays a documented rollover to
   `0%` with reset `--` after a known reset time has passed. Antigravity can show stale
   history, and OmniRoute receipt time leaves upstream age unknown. These distinctions
   keep the status line honest about what each source establishes.
5. **Keep provider access narrowly scoped.** Use the existing standard-library readers. When a
   change alters which files or services a reader accesses, update the corresponding privacy
   and data-flow documentation so users can understand what the status line reads.

## Review and merge gates

Follow these steps when preparing a Quotaline PR for a human merge decision.

- Run focused and full pytest, full Ruff, and the relevant CI checks on the latest PR commit.
  For status-line behavior, run an offline replay
  against expectations maintained independently of the proposed change.
- Obtain a completed Qodo review on that same latest SHA. On every new commit, rerun the checks
  and obtain a new completed review.
- Fix every valid High or Medium finding, regardless of finding type or source, and report Low
  findings even when they are not fixed. Do not silently dismiss findings.
- If a gate fails, allow at most one repair attempt. If gates remain unresolved, record the
  unresolved commands/findings and exact SHA, then stop for a human decision. Do not bypass,
  weaken tests, or change configuration to force a pass.
- Humans have merge authority. Agents must not merge, dismiss review findings, or alter branch
  protection or repository administration.
