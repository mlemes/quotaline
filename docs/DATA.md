# Data dictionary

This project stores no datasets. It reads three JSON inputs, and one more endpoint is recorded
for reference.

## Claude Code status line input (stdin)
- Source: Claude Code sends this JSON on each status line run. See https://code.claude.com/docs/en/statusline.
- Last checked: 2026-09-27, Claude Code v2.1.283

| Field | Type | Notes |
|---|---|---|
| `rate_limits.five_hour.used_percentage` | number | 0 to 100 |
| `rate_limits.five_hour.resets_at` | int | Unix epoch seconds |
| `rate_limits.seven_day.used_percentage` | number | 0 to 100 |
| `rate_limits.seven_day.resets_at` | int | Unix epoch seconds |

**Quirks:**
- `rate_limits` is present only for claude.ai Pro and Max subscribers, and only after the
  session's first API response.
- Each window can be absent independently. Claude Code drops a window once its `resets_at`
  time passes.

## Antigravity `retrieveUserQuotaSummary` response (used)
- Source: `POST https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary`
  with a Bearer token, `User-Agent: antigravity`, and body `{}`.
- Verified live on 2026-09-27: HTTP 200 with two groups.

| Field | Type | Notes |
|---|---|---|
| `groups[].displayName` | string | `Gemini Models`, `Claude and GPT models` |
| `groups[].description` | string | For example `Models within this group: Gemini Flash, Gemini Pro` |
| `groups[].buckets[].bucketId` | string | `gemini-5h`, `gemini-weekly`, `3p-5h`, `3p-weekly` |
| `groups[].buckets[].window` | string | `5h` or `weekly` |
| `groups[].buckets[].resetTime` | string | RFC 3339 UTC |
| `groups[].buckets[].remainingFraction` | number | 0 to 1. Treated as exhausted when missing |
| `description` | string | Top-level: "Within each group, models share a weekly limit and a 5-hour limit..." |

**Quirks:**
- Gemini Flash and Pro share one quota group. They are not tracked separately.
- Adding a `metadata` field to the request body returns HTTP 400. Send `{}`.
- The status line labels groups by the `bucketId` prefix (`gemini`, `3p`) and falls back to
  `displayName` for unknown groups.
- An unused 5-hour window shows `remainingFraction: 1`, and its `resetTime` rolls to about
  5 hours after the request until first use. Measured on 2026-09-27: Gemini weekly 14% used,
  Claude/GPT weekly 19% used.

## Codex session transcript `token_count` event (used)
- Source: Codex CLI writes `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<time>-<uuid>.jsonl`
  (`CODEX_HOME` defaults to `~/.codex`), one JSON object per line. The status line reads the
  last 256 KiB of up to 3 of the newest files and keeps the last matching event.
- Verified on 2026-09-28 with Codex CLI 0.158.0, from `codex exec` runs on the free plan and, after an upgrade and a fresh `codex login`, on the Go plan.

| Field | Type | Notes |
|---|---|---|
| `type` | string | `event_msg` |
| `timestamp` | string | RFC 3339 UTC. Base for the older `resets_in_seconds` |
| `payload.type` | string | `token_count` |
| `payload.rate_limits` | object or null | Null events are skipped |
| `payload.rate_limits.limit_id` | string | `codex`. Other IDs are skipped |
| `payload.rate_limits.plan_type` | string | `free` and `go` measured. Not used |
| `payload.rate_limits.primary`, `.secondary` | object or null | One window each |
| `<window>.used_percent` | number | 0 to 100 |
| `<window>.window_minutes` | int | 300 (5 hours) and 10080 (week) on paid plans, 43200 (30 days) on free and Go |
| `<window>.resets_at` | int | Unix epoch seconds. Older versions write `resets_in_seconds` instead |

**Quirks:**
- The free and Go plans each have one 30-day `primary` window and a null `secondary`, with no
  5-hour window. Measured on 2026-09-28: `used_percent` 0.0, `window_minutes` 43200 on both.
- After a plan upgrade, Codex keeps logging the old `plan_type` and limits until you run
  `codex logout` and `codex login`. Measured on 2026-09-28: a run after the upgrade still
  logged `free`, and the first run after a fresh login logged `go`.
- A window of 1440 minutes or less goes to the `session` column, and a longer one to the
  second column, labeled `week` or `<days>d`.
- The numbers are only as fresh as the last Codex response on this machine. A past `resets_at`
  means the window has reset since then, so the line shows `0%` and `--`.
- Before the first Codex run, `~/.codex/sessions/` doesn't exist, and the `threads` table in
  `~/.codex/state_5.sqlite` is empty. The rollout path is also stored there, in
  `threads.rollout_path`.
- Transcripts hold the full prompts and replies, and they can reach several MB. Never read a
  whole file.

## Antigravity `fetchAvailableModels` response (reference only, not used)
- Source: `POST https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels`
  with a Bearer token. `agy` calls this endpoint, as seen in `~/.gemini/antigravity-cli/cli.log`
  on 2026-09-27.
- Verified live on 2026-09-27: HTTP 200 with 27 models, on both `daily-cloudcode-pa` and
  `cloudcode-pa`. The request body is `{}`, and no project ID is needed.

| Field | Type | Notes |
|---|---|---|
| `models.<id>.quotaInfo.remainingFraction` | number | 0 to 1. Can be missing when the quota is exhausted |
| `models.<id>.quotaInfo.resetTime` | string | RFC 3339 UTC, for example `2026-09-27T18:00:00Z` |

**Quirks:**
- The request needs a non-default `User-Agent`. With the default `Python-urllib/3.x`, Google
  returns HTTP 403 even with a valid token. `User-Agent: antigravity` works.
- An unused model shows `remainingFraction: 1` and a `resetTime` about 5 hours after the
  request, so the window rolls forward until first use. The endpoint shows no weekly window,
  which is why the status line uses `retrieveUserQuotaSummary` instead.
- `v1internal:retrieveUserQuota` also works. It returns `{"buckets": [{"modelId",
  "remainingFraction", "resetTime", "tokenType": "WTUS"}]}`, including some internal
  `chat_NNNNN` IDs without `resetTime`.
- The `agy` model IDs seen on 2026-09-27 are `gemini-3.8/3.7/3.6-flash-{high,medium,low}`,
  `gemini-3.1-pro-{high,low}`, `claude-sonnet-4-6`, `claude-opus-4-6-thinking`, and
  `gpt-oss-120b-medium`.
- `agy` stores the OAuth token in the system keyring (log line `keyringAuth: loaded token`).
  Entry attributes: `service=gemini`, `username=antigravity`, and
  `xdg:schema=org.freedesktop.Secret.Generic`, with an empty label. The secret is JSON:
  `{"auth_method": "consumer", "id_token", "token": {"access_token", "expiry",
  "refresh_token", "token_type"}}`. The access token lasts about one hour, and only `agy`
  refreshes it.
