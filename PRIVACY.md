# Privacy policy

Effective date: September 27, 2026

This policy covers the quotaline Claude Code plugin and the `usage-statusline` code it runs. The
author, Marcus Lemes, doesn't operate any server for quotaline and doesn't receive any data from
it.

## What the author collects

Nothing. quotaline has no telemetry, analytics, crash reporting, or update checks of its own.

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

## What quotaline stores on your machine

quotaline writes only these files, all on your machine:

- `~/.claude/settings.json`: the `statusLine` entry, plus a one-time backup of the file at
  `~/.claude/settings.json.bak-usage-statusline`.
- `~/.config/usage-statusline/agy_token_cmd`: the `secret-tool lookup` command that reads the
  token, built from the keyring entry's attributes. For `agy`'s own entry, the attributes are
  `service=gemini` and `username=antigravity`. If you pick a different entry, the command holds
  that entry's attributes, which can include an email address.
- `~/.cache/usage-statusline/antigravity.json`: the formatted quota percentages and reset times.
- A copy of the plugin's code in the plugin's data directory, under `~/.claude/plugins/data/`.

## What quotaline sends, and to whom

- **Google.** When you set up the Antigravity line, quotaline sends the `agy` access token to
  `daily-cloudcode-pa.googleapis.com`, Google's API, which issued the token. The request body
  is empty (`{}`), and the response contains your quota percentages and reset times. quotaline
  makes this request once during `/quotaline:install`, and then at most once every 60 seconds
  from the status line. Google handles this request under its own
  [privacy policy](https://policies.google.com/privacy). If you install with `--no-agy` and
  have no saved token command, quotaline sends nothing.
- **Anthropic, through Claude Code.** `/quotaline:install` and `/quotaline:uninstall` run in
  your Claude Code session, so their output becomes part of that session. That output includes
  the setup messages and the quota lines. If several keyring entries match during setup, it also
  includes their labels and attributes. Claude Code handles your session under Anthropic's
  terms and privacy policy.

quotaline sends nothing else to anyone.

## Delete your data

1. Run `/quotaline:uninstall`. It removes the `statusLine` entry and the code copy.
2. Delete the files that uninstall keeps:

   ```bash
   rm -rf ~/.config/usage-statusline ~/.cache/usage-statusline
   rm ~/.claude/settings.json.bak-usage-statusline
   ```

   Check the backup before you delete it, because it's a copy of your settings from before the
   first install.

3. Run `claude plugin uninstall quotaline@mlemes`.

## Changes and contact

Changes to this policy appear in this file's history on GitHub. To ask a question about privacy,
[open an issue](https://github.com/mlemes/quotaline/issues).
