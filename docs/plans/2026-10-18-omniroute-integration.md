# OmniRoute Integration Implementation Plan

**Status:** Approved for implementation on `feat/omniroute-integration` in the isolated
`/tmp/quotaline-omniroute-worktree`. Installed `/home/mlemes/Projects/quotaline` must remain
untouched. No activation, push or merge. Tests precede implementation; different models own
those roles and review. The user authorized this optional integration after Phase 0.

**Goal:** Explicitly configured installations read selected subscription quotas from local
OmniRoute; installations without configuration keep their existing behavior.

## Phase 0 result and source policy

The scoped usage-capable key successfully read
`http://127.0.0.1:20128/api/usage/om-usage?format=json`. The live response on October 18–19,
2026 includes `agy`, `claude` and `codex` snapshots in `providers`, each with an opaque
`connectionId`. The singular `provider` is a router preference, and `personal` is the key's
router budget; neither chooses or supplies subscription rows.

Live data disproved the provisional source-level concern about missing Antigravity weekly
keys: `gemini_weekly`, `claude_gpt_weekly` and `gemini_4_argon_weekly` are all available.
Gemini and Claude/GPT family models currently share their respective percentage/reset pairs;
Argon has a separate weekly reset. The adapter must still reject missing or inconsistent
future data rather than assume this remains true.

OmniRoute does not expose the upstream observation timestamp. Local receipt is a polling
throttle, never proof of provider freshness. Every configured output has one global
`OmniRoute … upstream age unknown` header.

Source policy is now fixed: absent config uses native readers unchanged; existing config
uses **only OmniRoute** for the explicitly selected connections. Errors remain visible and
may retain mapping-bound stale router data. No native fallback, inferred account equivalence,
provider-window blending, duplicate native section or runtime mode selector. Removing the
config restores native mode.

## Scope, interfaces and ownership

Use Python's standard library and existing `claude.fmt_line`/`fmt_windows`. No dependency,
service, background polling, inference, provider credential import/refresh, router settings
change, endpoint discovery or native cache refactor.

- Test writer: `tests/test_omniroute.py`, router cases in `tests/test_smoke.py`, sanitized
  `tests/fixtures/omniroute.json`, and minimum importable module stubs. Test writer never
  implements production function bodies.
- Implementer: `src/usage_statusline/omniroute.py` and the small source-selection branch in
  `src/usage_statusline/main.py`; never edits tests.
- Independent reviewer: read-only review of implementation, tests and documentation.
- Architect: exact brief, red/green confirmation, line-by-line security review, documentation,
  full gate and feature-branch commit. No push, merge or activation.

Adapter interfaces:

```python
parse_connection(snapshot: dict, selection: dict) -> list[str]
fetch_snapshot(key: str) -> dict
omniroute_lines(config: Path = CONFIG, cache: Path = CACHE,
                now: float | None = None) -> str | None
```

`None` means only absent configuration. `main` checks the adapter before stdin/native readers;
configured output or adapter failure prints and returns. Unexpected adapter errors must also
fail visibly without calling native readers.

The exact handoff brief is `/tmp/quotaline-omni-implementation-brief.md`. The temporary
sanitized fixture `/tmp/quotaline-omni-fixture.json` contains fake IDs, selected quota fields,
and deliberate irrelevant `personal`/preferred-provider data. Neither the private live capture
nor the key belongs in the repository.

## Configuration, identity and transport

One file: `~/.config/usage-statusline/omniroute.json`:

```json
{
  "key_file": "/absolute/private/usage-key-file",
  "connections": [
    {"provider": "claude", "connection_id": "selected-claude-id"},
    {"provider": "agy", "connection_id": "selected-agy-id", "alias": "work"},
    {"provider": "codex", "connection_id": "selected-codex-id"}
  ]
}
```

Reject unsupported keys, malformed config, unknown provider, empty/duplicate IDs and control
characters. Optional aliases are short printable display strings appended to standard labels.
Select by exact ID and exact provider from `providers`; missing, duplicated or mismatched
selected snapshots are errors. Unselected connections and unknown quota keys do not render.

Read only the referenced usage key file; no automatic credential discovery. Recommend private
mode `0600` for key/config. GET only the fixed loopback endpoint with an unredirected Bearer
header, two-second timeout, disabled environment proxies and all redirects rejected. Never
put the key in argv, URL, logs, errors, cache or fixtures. HTTP 401 reports rejected usage key;
403 reports usage permission required. No alternate key, refresh, permission edit or retry.
Other failures use static sanitized errors without raw response/identity/exception text.

## Quota contract

Reject bool, strings, nonfinite or out-of-range numbers, unlimited windows and missing/invalid
or timezone-naive resets. Preserve percentages and resets even after reset time passes.

- Claude exact keys `session (5h)` and `weekly (7d)` use `used` percent with `total=100`.
  Require both. Optional remainingPercentage must agree within 0.1 percentage point.
- Codex recognized keys `session` and `weekly` also use `used`/`total=100`, with at least
  one valid window. Positive integer `windowSeconds` determines placement: at most one
  <=86400-second session and one longer window. The second column is `week` for 604800
  seconds, otherwise the whole-day duration, such as `30d`. A single long window leaves
  the session column absent. Never infer duration from a quota key alone.
- Antigravity percentages are `100-remainingPercentage`; its integer `used`/`total=1000`
  fields are rounded and must not replace the precise percentage. Gemini session comes
  from agreeing `gemini-*` model pairs excluding `gemini-4-argon-*`; Claude/GPT session
  comes from agreeing `claude-*`/`gpt-*` pairs. If any recognized candidates disagree in
  percentage or reset, report inconsistency rather than select one. Weekly keys are exactly
  `gemini_weekly`, `claude_gpt_weekly`, `gemini_4_argon_weekly`. Require all five group/window
  pairs. Argon always has no session; per-model Argon resets never create one.

Each AG connection is an atomic three-row result. A missing/invalid required window fails
that connection, preserving its previous complete result as stale when available. This avoids
joining fresh and old quota windows. Valid other connections still update independently.

## Cache and freshness

Use a separate `~/.cache/usage-statusline/omniroute.json`, atomic private `0600` replacement,
and best-effort storage. Persist a version, canonical config fingerprint, last attempt time,
rendered output, and per-selected-connection pristine successful rows with local receipt time.
Do not store keys, raw responses, unselected data, account names or key paths. IDs remain
opaque mapping keys. Config/alias/order/key-file path changes invalidate scope.

Successful and failed attempts throttle requests for 60 seconds when storage works. Invalid,
corrupt, nonfinite, bool or future cache timestamps are misses. Validate cached shape/rows;
broken storage cannot hide freshly fetched output. Failed connections keep only their own
previous successful rows, annotated `stale (received YYYY-MM-DD HH:MM)`, plus current error.
Healthy connections replace their prior rows. Failures never advance successful receipt time
or accumulate stale suffixes. The global header always says upstream age unknown.

## Execution and gates

1. Test writer covers config/source switching, exact identity, live-sanitized quota semantics,
   numeric/reset edge cases, AG inconsistency and Argon weekly-only behavior, Codex duration,
   auth/proxy/redirect non-disclosure, throttling, partial stale retention, scope changes,
   malformed cache, private atomic writes and storage failures.
2. Architect personally runs focused tests, confirms the intended red failures, then authorizes
   implementation. Implementer runs focused checks after adapter and cache/main chunks.
3. Architect reruns focused and full tests. Independent reviewer reviews production and test
   diff. Implementer applies accepted findings; test writer alone corrects any invalid tests.
4. Architect updates README, PRIVACY, docs/DATA.md, docs/architecture.md and docs/data_flow.md
   to the actual implementation, including setup/permissions, source selection, stale/unknown
   freshness, data deletion and rollback. Update package/plugin versions together to 0.3.0.
5. Architect runs full pytest, Ruff lint, Ruff format check, ty on src, `bash -n install.sh`,
   `claude plugin validate .`, and `git diff --check`. No self-reported pass substitutes.
6. Isolated live read uses explicit temporary config/cache and worktree PYTHONPATH only.
   Measure native/router calls and latency; no inference or provider-refresh benchmark.
7. Final review covers touched-file scope, both core docs, secrets/identity/redirect/cache
   code, and unchanged installed main. Commit the verified feature branch only.

## Source provenance and limitations

Pinned OmniRoute v3.8.51 sources informed initial investigation:

- [Usage auth and snapshots](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.51/src/lib/usage/internalUsageCommand.ts)
- [Quota normalization](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.51/src/lib/usage/providerLimits/quotaNormalize.ts)
- [Antigravity weekly parsing](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.51/open-sse/services/usage/antigravityWeeklyQuota.ts)

Live evidence supersedes the initial inference that normalization removed weekly aggregates.
Cached-only GET does not establish freshness, trigger provider refresh or reduce OmniRoute's
own polling. Supported field names are internal contracts and may change. Such changes must
fail visibly, with stale historical values where available, rather than inventing quota data.
