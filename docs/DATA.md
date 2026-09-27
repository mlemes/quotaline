# Data dictionary

This project stores no datasets. It reads two JSON inputs.

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

## Antigravity `fetchAvailableModels` response
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
  request, so the window rolls forward until first use. The endpoint shows no weekly window.
- `v1internal:retrieveUserQuota` also works. It returns `{"buckets": [{"modelId",
  "remainingFraction", "resetTime", "tokenType": "WTUS"}]}`, including some internal
  `chat_NNNNN` IDs without `resetTime`.
- The `agy` model IDs seen on 2026-09-27 are `gemini-3.8/3.7/3.6-flash-{high,medium,low}`,
  `gemini-3.1-pro-{high,low}`, `claude-sonnet-4-6`, `claude-opus-4-6-thinking`, and
  `gpt-oss-120b-medium`. The GPT-OSS model is not shown.
- `agy` stores the OAuth token in the system keyring (log line `keyringAuth: loaded token`).
  Entry attributes: `service=gemini`, `username=antigravity`, and
  `xdg:schema=org.freedesktop.Secret.Generic`, with an empty label. The secret is JSON:
  `{"auth_method": "consumer", "id_token", "token": {"access_token", "expiry",
  "refresh_token", "token_type"}}`. The access token lasts about one hour, and only `agy`
  refreshes it.
