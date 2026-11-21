---
name: quotaline-quota-replay
description: Verify Quotaline's native Claude quota display on an exact head by replaying the base-owned checker or checking its published GitHub Actions evidence.
---

# Quotaline quota replay

Verify the native Claude quota display on a trusted runner with the synthetic checker from the
exact public base. Keep the expected output outside the candidate. Use the checker's synthetic
inputs and an environment free of provider credentials, real session files and transcripts.

## Inputs and provenance

Require immutable checkouts or Git exports, not a working tree of unknown state:

- `BASE`: public base commit containing `scripts/quota_acceptance.py`.
- `HEAD`: public candidate commit to test. The checker reads only `HEAD/src`.
- `EVIDENCE`: empty directory outside both trees for this replay's logs.

Record the public repository, full commit SHAs and input provenance. For Git checkouts, verify
each root and commit. The status commands must return no entries, including ignored files in
the checker, candidate source and workflow paths. A fresh verified export also works.

```bash
git -C "$BASE" rev-parse --show-toplevel HEAD
git -C "$HEAD" rev-parse --show-toplevel HEAD
git -C "$BASE" status --porcelain --ignored --untracked-files=all -- scripts .github/workflows
git -C "$HEAD" status --porcelain --ignored --untracked-files=all -- src .github/workflows
git -C "$BASE" show HEAD:scripts/quota_acceptance.py | cmp - "$BASE/scripts/quota_acceptance.py"
```

For Git tar exports, check each archive checksum and `git get-tar-commit-id` against trusted
provenance. Extract the verified archives into two empty scratch directories and replay those
trees. File times and ownership can change when an export is copied. If identity, cleanliness
or the base checker is uncertain, stop inconclusive. Keep both input trees unchanged.

## Hosted evidence

Use this path for an existing GitHub Actions run. Obtain job metadata and the matching log from
GitHub or a trusted export of that job. Record the repository, run and job links, attempt, and
conclusion. Check that the completed `Independent acceptance (base-owned checker)` job and its
run name the requested head. Confirm the reviewed workflow is unchanged between the supplied
base and head. Match the `git log -1 --format=%H` output from both checkouts to the requested
SHAs, then check the logged command ran the base's checker against candidate source in container
mode.

Read the case names and expected stdout from the immutable base checker. For a completed
suite, require one verdict per full-suite case and reconcile the tally, final summary, checker
exit and job conclusion. For a stdout failure, compare the logged strings with the base
expectation, preserving spaces. A successful step may imply exit zero. Label that exit as
inferred.

If a per-case timeout, failed runner invocation or container status 125, 126 or 127 stops the
suite, verify the contiguous earlier verdicts against the base case order, the next case's
named `INCONCLUSIVE` reason, and exit 2. Record inconclusive without assigning verdicts to
unrun cases. For older bases, use the historical interpretation below. Record inconclusive if
the job evidence is missing, stale or inconsistent.
Label the result as verification of hosted output and record that no new replay ran locally.

## Local replay

Use the base checker's restricted Docker container for every local replay. Check that
`docker image inspect <image>` succeeds for the pinned image in
`$BASE/scripts/quota_acceptance.py`. If Docker or the image is unavailable, verify a matching
hosted job or record an inconclusive result. Capture the local output and the checker's exit
status with Bash.

```bash
set +e
python3 -I -B "$BASE/scripts/quota_acceptance.py" "$HEAD" --container 2>&1 | tee "$EVIDENCE/acceptance.log"
status=${PIPESTATUS[0]}
set -e
printf 'exit=%s\n' "$status"
```

## Interpret and record

- `0` with an `OK` summary means the replay passed. Record the counts.
- `1` with a `FAILED` summary means an evaluated candidate mismatched. Record the counts
  and case names. In host mode, candidate exits 125, 126 or 127 are ordinary mismatches.
- `2` means inconclusive. For a per-case timeout, invocation error or container status
  125, 126 or 127, the checker preserves earlier rows and stops with
  `INCONCLUSIVE <case>: <reason>`. Record the affected case and reason. The reserved Docker
  statuses leave attribution uncertain.
- For older base commits, use the recorded base SHA and observed runner or infrastructure
  evidence to identify an inconclusive result, even if the checker printed `FAIL` and exited
  `1`. Preserve an observed candidate assertion or exit status in host mode as candidate
  evidence. Record inconclusive for missing or ambiguous evidence.

Save the recorded SHAs and provenance, exact command, numeric exit code, pass/fail counts,
failed case names and a bounded excerpt of the synthetic output. Report one verdict: passed,
asserted failure, or inconclusive. Stop at the first unresolved tool or evidence problem and
name what is missing. This replay only writes evidence.
