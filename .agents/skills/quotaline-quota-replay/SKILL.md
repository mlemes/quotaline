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
that each checkout root and its HEAD match the inputs and that both trees are clean.

```bash
git -C "$BASE" rev-parse --show-toplevel HEAD
git -C "$HEAD" rev-parse --show-toplevel HEAD
git -C "$BASE" status --porcelain
git -C "$HEAD" status --porcelain
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

Read the case names and expected stdout from the immutable base checker. Require exactly one
verdict for every full-suite case. For a stdout failure, compare the logged expected and actual
strings with the base expectation, preserving spaces, and report the observed difference.
Reconcile the case tally, final summary, checker exit and job conclusion. On a successful step,
an exit of zero may be inferred from the runner result and must be labeled as inferred.
Stop inconclusive if records are missing, stale, inconsistent, or show a runtime failure.
Label the result as verification of hosted output and record that no new replay ran locally.

## Local replay

`--container` requires Docker already installed and the pinned image already present locally. Confirm with `docker image inspect <image>`, using the image named in `$BASE/scripts/quota_acceptance.py`; do not let the checker pull it. Use the offline option below if its requirements are met. Otherwise stop inconclusive. Run the base checker against the exact head and capture everything:

```bash
set +e
python3 -I -B "$BASE/scripts/quota_acceptance.py" "$HEAD" --container 2>&1 | tee "$EVIDENCE/acceptance.log"
status=${PIPESTATUS[0]}
set -e
printf 'exit=%s\n' "$status"
```

Use the same command without `--container` only when both input trees are reviewed public
sources and the execution environment independently blocks network access and keeps credentials
out of reach. Record how that boundary was established.

## Interpret and record

The checker prints `quota acceptance: N cases (container|local host)`, one `PASS` or `FAIL` per case, then `OK: N cases passed` or `FAILED M/N cases: ...`.

- `0` with an `OK` summary: replay passed. Record the counts.
- `1` with a `FAILED` summary where every `FAIL` shows stdout, stderr or exit-status mismatch: asserted failure. Record pass/fail counts and the first failing case name.
- `2`: usage or setup failure (invalid repo root or symlink, missing Docker, image preparation). Inconclusive.
- `1` without complete per-case verdicts, or with launch errors, Docker startup failures,
  or timeout: inconclusive.

Save the recorded SHAs and provenance, exact command, numeric exit code, pass/fail counts,
failed case names and a bounded excerpt of the synthetic output. Report one verdict: passed,
asserted failure, or inconclusive. Stop at the first unresolved tool or evidence problem and
name what is missing. This replay only writes evidence.
