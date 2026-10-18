# Antigravity usage reliability implementation plan

Goal: restore Gemini quota display and recover expired credentials without an interactive Antigravity session, while preserving the Claude Code plugin contract.

Design: retain retrieveUserQuotaSummary for explicitly named windows. Supplement absent Gemini groups with fetchAvailableModels on the same Google host, using its quota/reset values without claiming a weekly window. Keep credential refresh in agy through a bounded, non-interactive `agy models` subprocess, only for expired credentials or HTTP 401. Preserve last successful lines with a timestamp and an explicit stale marker when retrieval fails.

Constraints: standard library only; no stored tokens, new OAuth client, keyring writes by quotaline, or changed installer/skill/hook interfaces. Refresh may invoke agy's normal startup behavior; document this. Preserve legacy cache reads. Both package and plugin versions advance to 0.2.1.

1. Add regression tests and observe failures: summary without Gemini, model quota fallback and missing values, partial endpoint failure, expired credentials and 401 retry, cache failure recovery and read-only storage, malformed data, provider isolation.
2. Implement quota retrieval and bounded refresh in src/usage_statusline/antigravity.py. Reuse existing layout, with a `quota` label for model-level data. Keep last successful endpoint data when only one endpoint fails.
3. Make cache writes atomic and optional. Retain successful output on errors, mark every stale line with observation time, and throttle failed retries for 60 seconds. Isolate exceptions in main.py so one provider never suppresses another.
4. Update README.md, PRIVACY.md, docs/DATA.md and docs/ARCHITECTURE.md for endpoints, refresh subprocess, cache semantics and limits. Update version metadata.
5. Run complete pytest suite, Ruff, installer/plugin checks and a live fetch without printing secrets. Review final diff. Commit and push main; verify remote commit.
6. Open the supplied Anthropic submission page in a browser, read status if authenticated, and report any authentication/access blocker without changing the submission.

Acceptance: Gemini displays real API usage with no fabricated weekly number; Claude/GPT remains available on Gemini failure; expired credentials trigger one bounded refresh; failures retain visibly stale values; cache/provider failures do not suppress Claude or Codex; plugin validation and regression suite pass.

## Execution evidence

- Original 48 tests passed before changes. Initial regression suite failed in 11 cases.
- Added endpoint fallback, auth recovery, stale-cache, malformed-data and storage failure coverage.
- Independent review found a token-reread timeout that discarded healthy summary output.
  The regression failed before the fix and passed afterward; full suite: 73 tests.
- Ruff lint/format, installer shell syntax and Claude plugin marketplace validation passed.
- Submission status access reached a Cloudflare HTTP 403 security-verification page; no
  submission data was visible and no submission fields were changed.
- Live model endpoint confirmed Gemini quota with the existing credentials; transient request
  failures remain possible and are represented explicitly rather than replacing successful data.
