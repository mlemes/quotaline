# Privacy policy

Effective date: October 19, 2026

This policy covers the quotaline Claude Code plugin and the `usage-statusline` code it runs. The
author, Marcus Lemes, doesn't operate any server for quotaline and doesn't receive any data from
it.

## What the author collects

Nothing. quotaline has no telemetry, analytics, crash reporting, or update checks of its own.

## Optional local OmniRoute mode

Without `~/.config/usage-statusline/omniroute.json`, the native behavior below applies.
With that file, runtime uses only the explicitly selected OmniRoute connections; it does
not read Claude stdin usage, the Antigravity keyring/token command or Codex transcripts,
and does not run native requests or `agy models`. Installation still performs native
Antigravity setup unless `--no-agy` is passed.

quotaline reads the config's supported provider names, opaque connection IDs, optional
aliases and referenced key-file path. It reads that key file into memory only for a fetch,
and sends its Bearer key exclusively to the fixed loopback URL
`http://127.0.0.1:20128/api/usage/om-usage?format=json`. Environment proxies are disabled
and redirects are rejected. It does not read provider credentials or change router keys,
permissions or settings. The user supplies a usage-permitted key; no inference is submitted.
OmniRoute retains ownership of its provider polling, credentials, storage and privacy behavior.

The response includes connection quota snapshots and can include unrelated fields; quotaline
uses only explicitly mapped provider/ID pairs and subscription quota fields. It discards
unselected connections, raw responses and the router key's personal budget. Display errors
never include credentials, connection IDs, raw response text or exception messages.

`~/.cache/usage-statusline/omniroute.json` stores selected formatted rows, selected opaque
connection IDs, a configuration fingerprint and local attempt/receipt timestamps. Temporary
sibling files allow atomic private `0600` replacement. No key, key-file path, raw response or
unselected account data is cached. Protect the config and key file with `chmod 600`; aliases
are displayed, so choose them accordingly. Receipts do not establish upstream freshness.
Stale rows can persist without a maximum age, clearly labeled with their original receipt.

Removing or renaming the config restores native mode. Deleting the OmniRoute config/cache
and the referenced key file removes this integration's local data; key files outside the
quotaline directory need to be deleted separately. Revoke the dedicated key in OmniRoute
if you no longer use it. quotaline never deletes or revokes router/provider credentials itself.

## What quotaline reads on your machine

- **Claude Code's status line JSON.** quotaline uses only the `rate_limits` field and discards
  the rest.
- **Keyring labels and attributes, during setup only.** To find the Antigravity (`agy`) token,
  `/quotaline:install` lists the labels and attributes of your system keyring entries. These can
  contain account names or email addresses. quotaline keeps them in memory only and never writes
  them to disk, except as described under "What quotaline stores".
- **The `agy` keyring secret.** It holds an OAuth access token, and it can also hold an ID token
  that contains your Google account name and email. quotaline keeps only the access token and
  discards everything else. It never prints, logs, or saves either token.
- **Codex session transcripts.** To show the Codex line, quotaline reads the last 256 KiB of up
  to 3 of the newest files under `~/.codex/sessions/` (or `$CODEX_HOME/sessions/`). It uses only
  the `rate_limits` field of the last `token_count` event. The rest, which includes your prompts
  and Codex's replies, is discarded in memory and never stored or sent. quotaline doesn't read
  `~/.codex/auth.json`, makes no network request for this line, and writes nothing for it.

## What quotaline stores on your machine

quotaline writes the optional cache described above and these native/install files, all on your machine:

- `~/.claude/settings.json`: the `statusLine` entry, plus a one-time backup of the file at
  `~/.claude/settings.json.bak-usage-statusline`.
- `~/.config/usage-statusline/agy_token_cmd`: the `secret-tool lookup` command that reads the
  token, built from the keyring entry's attributes. For `agy`'s own entry, the attributes are
  `service=gemini` and `username=antigravity`. If you pick a different entry, the command holds
  that entry's attributes, which can include an email address.
- `~/.cache/usage-statusline/antigravity.json`: formatted quota percentages, reset times,
  successful rows and observation timestamps. Temporary sibling files allow atomic replacement.
- A copy of the plugin's code in the plugin's data directory, under `~/.claude/plugins/data/`.

## What quotaline sends, and to whom

- **Google.** When Antigravity is configured, quotaline sends its `agy` access token to
  `daily-cloudcode-pa.googleapis.com` for `retrieveUserQuotaSummary` and, when Gemini is
  missing, `fetchAvailableModels`. Both requests have body `{}`, send
  `User-Agent: antigravity/cli/1.4.2`, and return quota/model data.
  It runs one fetch cycle during setup and then at most once per 60 seconds when the cache is
  writable. An HTTP 401 permits one refresh attempt and one retry of the failed request.
  Google handles requests under its [privacy policy](https://policies.google.com/privacy).
  Without a saved or environment-configured token command, no requests are made.
- **Credential recovery through agy.** On HTTP 401, quotaline can invoke the installed
  `agy models` command without interactive input. It discards command output, bounds runtime
  to 10 seconds, and terminates its process group afterward. `agy` owns refresh credentials
  and any keyring updates; quotaline never stores or sends refresh tokens itself. `agy` may
  initialize configured plugins, write its normal logs/state, and make its own authentication,
  model-listing or startup requests. Its behavior and privacy settings remain those of `agy`.
- **Anthropic, through Claude Code.** `/quotaline:install` and `/quotaline:uninstall` run in
  your Claude Code session, so their output becomes part of that session. That output includes
  the setup messages and the quota lines. If several keyring entries match during setup, it also
  includes their labels and attributes. Claude Code handles your session under Anthropic's
  terms and privacy policy.

quotaline itself sends nothing else to anyone. The delegated `agy` command retains its own
network and storage behavior, as described above.

## Delete your data

1. Run `/quotaline:uninstall`. It removes the `statusLine` entry and the code copy.
2. Delete the files that uninstall keeps:

   ```bash
   rm -rf ~/.config/usage-statusline ~/.cache/usage-statusline
   rm ~/.claude/settings.json.bak-usage-statusline
   ```

   Check the backup before you delete it, because it's a copy of your settings from before the
   first install. Delete the referenced OmniRoute key file separately if it lives outside
   this directory; revoke its key in OmniRoute if no longer needed.

3. Run `claude plugin uninstall quotaline@mlemes`.

## Changes and contact

Changes to this policy appear in this file's history on GitHub. To ask a question about privacy,
[open an issue](https://github.com/mlemes/quotaline/issues).
