# Data flow

How data enters, changes, is stored, and leaves `usage_statusline` on one status line run.
Field-level formats are in `docs/DATA.md`; components and decisions are in
`docs/architecture.md`.

## 1. Entry: `main.main()` (`src/usage_statusline/main.py`)

- Input: Claude Code runs `python3 -m usage_statusline` after each update and every 60 s, with
  status line JSON on stdin. Invalid JSON or a non-object value becomes `{}`.
- Output: plain text lines on stdout, in order: Claude, Antigravity (one or more), Codex (optional).
- Provider isolation: `claude_line()` and `antigravity_line()` are independently wrapped in
  `except Exception`; a failure prints the provider label and `n/a (<ExceptionName>)` while
  the other providers still render. Only the exception type name is printed, never its message.
  `codex_line()` handles its own exceptions internally.

## 2. Claude line: `claude.claude_line(data)` (`src/usage_statusline/claude.py`)

- Input: `rate_limits.five_hour` and `rate_limits.seven_day` from stdin (percent, epoch reset).
- Output: one row via `fmt_line`/`fmt_windows`. No network, no files.

## 3. Antigravity lines (`src/usage_statusline/antigravity.py`)

### 3a. Throttle: `antigravity_line(cache=CACHE, now=None)`

1. Reads `~/.cache/usage-statusline/antigravity.json`. If `0 <= now - fetched_at < CACHE_TTL`
   (60 s) and `line` is a string, returns `line` with no fetch. Errors are throttled the same way.
2. Otherwise loads `successful` (`{label: [row, observed_epoch]}`). A legacy cache (`fetched_at`,
   `line` only) without `n/a` or `stale` is converted to `successful` keyed by row label.
   Unreadable or malformed cache is ignored.
3. Calls `fetch_line()` (3b).

### 3b. Fetch: `fetch_line()`

1. Token command: `token_cmd()` returns `USAGE_STATUSLINE_AGY_TOKEN_CMD` or the text of
   `~/.config/usage-statusline/agy_token_cmd` (written by `agy_setup.py`, normally
   `secret-tool lookup <attrs>`). `shlex.split` turns it into argv.
2. **Trust boundary, keyring to process memory.** `read_token()` runs argv with
   `subprocess.run(shell=False, capture_output=True, timeout=TIMEOUT)` (2 s). stdout is the raw
   keyring secret; `extract_token()` reduces it to the access token (plain, oauth2 JSON,
   `{"token": {...}}` wrapper, or `go-keyring-base64:`). The token lives only in local variables.
   It is never written to disk, cached, printed, or put in an error row.
3. **Trust boundary, process to Google.** `request(endpoint)` POSTs `{}` with
   `Authorization: Bearer <token>`, `Content-Type: application/json` and
   `User-Agent: antigravity/cli/1.4.2`, timeout 2 s, to:
   - `https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary`
   - `https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels`, only when the
     summary has no `AG Gemini` group or the summary request failed.
   The Authorization header is unredirected, so a redirect cannot forward the Bearer token.
   Responses are parsed as JSON (untrusted input) and never executed.
4. Parsing: `parse_summary()` gives `(label, 5h, weekly)` per group, rendered by
   `format_lines()`. The `gemini-argon-` bucket prefix maps to `AG Argon` before generic Gemini
   matching; unknown groups retain their display names. Argon's weekly-only bucket leaves
   the session column empty. The CLI User-Agent exposes groups omitted by bare `antigravity`.
   Invalid fraction types, non-finite values and fractions outside `[0, 1]`
   are skipped per bucket; missing summary fractions retain the exhausted interpretation. `parse_models()` keeps Gemini, non-internal models with a finite fraction in
   `[0, 1]` and a reset time, merges identical `(fraction, reset)` pairs, and renders `quota`
   rows (no weekly claim). Models with missing or invalid values are dropped, not shown as 0%.
5. Errors: each endpoint fails independently into its own row,
   `<label>  n/a (HTTP <code>|fetch failed; run agy to check login)`. Only the HTTP status code
   appears. A summary failure does not suppress the Gemini model rows, and vice versa.
6. Output: newline-joined rows.

### 3c. HTTP 401 refresh: `refresh_login()`

- Trigger: the first HTTP 401 in a `fetch_line()` call (`refreshed` is shared by both
  endpoints, so at most one refresh per fetch).
- Ownership: quotaline never refreshes OAuth or writes the keyring. It runs
  `agy models` (resolved with `shutil.which`) with stdin, stdout, and stderr set to `DEVNULL`, in
  a new session (`start_new_session=True`), so `agy` uses its own refresh token and keyring.
- Timeout: `REFRESH_TIMEOUT` (10 s). Exit code 0 counts as success; timeout or non-zero fails.
- Cleanup: in all cases `os.killpg(pid, SIGKILL)` kills the process group, then the `Popen`
  context waits for the child. Children that leave the group (own `setsid`) are not killed.
- After success, `read_token()` rereads the keyring and the same request is retried once. A
  failed refresh or empty token re-raises the original 401.

### 3d. Merge, stale rows, storage (back in `antigravity_line`)

1. Rows containing `n/a` or `no quota data` are errors; all other rows are successful and stored
   as `successful[label] = [row, now]`.
2. If any error row exists, each previous `successful` label not refreshed this cycle is shown as
   `<row> · stale (updated YYYY-MM-DD HH:MM)` in local time and kept with its original
   observation time. Error rows follow. Stale rows have no maximum age.
3. Write: `{"fetched_at", "line", "successful"}` goes to a `NamedTemporaryFile` (mode 0600) in the
   cache directory, then `Path.replace` swaps it in atomically; the temp file is removed on
   failure. Any `OSError` is ignored, so rendering continues, but the 60 s throttle is lost and
   every run fetches (and may refresh) again.
4. Stored data: rendered rows and epoch timestamps only. No token, account ID, or raw response.
5. Output: the merged rows go back to `main`.

## 4. Codex line: `codex.codex_line()` (`src/usage_statusline/codex.py`)

- Input: last 256 KiB of up to 3 newest `$CODEX_HOME/sessions/**/rollout-*.jsonl`.
- Output: one row, or nothing when the sessions directory is missing. No network, no cache.
