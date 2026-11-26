#!/usr/bin/env python3
"""Independent acceptance checks for the Quotaline status-line CLI.

Usage:
    python3 scripts/quota_acceptance.py REPO_ROOT [--controls-only] [--container]

The checker runs the usage_statusline entry point in a fresh interpreter and compares exact
stdout, empty stderr and the exit status. Expected output lives here, outside the candidate
process. Only REPO_ROOT/src is injected on the child's sys.path; the other provider callables
are replaced before the CLI module runs.

Without --container the child gets a cleared environment, an empty HOME, a UTC/C locale and an
empty working directory. With --container the child runs in the pinned official Python image
with no network, a read-only root, no capabilities, an unprivileged user and only the target
src mounted read-only. The host environment and credentials are never passed in.

The full run includes the baseline controls. --controls-only runs just those controls.
"""

import argparse
import errno
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

IMAGE = "python:3.13-slim@sha256:48d884813cf44e927cf64c5529dd630dd3b18338c6dc727991eef9b71e934a20"
TIMEOUT = 20
FIXED_RESET = 1738425600
RESET_TEXT = "Sat 16:00"

# Run only the Claude path. The other providers are replaced after importing main, before the
# package's __main__ runs.
CHILD_CODE = r"""
import runpy
import sys

sys.path.insert(0, sys.argv[1])

import usage_statusline.main as target


def _absent():
    return None


target.omniroute_lines = _absent
target.antigravity_line = _absent
target.codex_line = _absent
target.opencode_line = _absent

runpy.run_module("usage_statusline", run_name="__main__")
"""


@dataclass(frozen=True)
class Case:
    name: str
    stdin: str
    expected_stdout: str


def _json(data: object) -> str:
    return json.dumps(data, separators=(",", ":"))


CONTROL_CASES = (
    Case(
        "normal-fixed-reset",
        _json(
            {
                "rate_limits": {
                    "five_hour": {"used_percentage": 37, "resets_at": FIXED_RESET},
                    "seven_day": {"used_percentage": 41, "resets_at": FIXED_RESET},
                }
            }
        ),
        f"Claude         session  37% · resets {RESET_TEXT} | week  41% · resets {RESET_TEXT}\n",
    ),
    Case(
        "reset-only-hidden",
        _json({"rate_limits": {"five_hour": {"resets_at": FIXED_RESET}}}),
        "",
    ),
    Case("clean-absent-hidden", "", ""),
    Case("malformed-input-hidden", "{not json", ""),
)

FULL_CASES = CONTROL_CASES + (
    Case(
        "37-reset-omitted",
        _json({"rate_limits": {"five_hour": {"used_percentage": 37}}}),
        "Claude         session  37% · resets --        | week   --\n",
    ),
    Case(
        "37-reset-null",
        _json({"rate_limits": {"five_hour": {"used_percentage": 37, "resets_at": None}}}),
        "Claude         session  37% · resets --        | week   --\n",
    ),
    Case(
        "zero-reset-omitted-plus-41-week-fixed-reset",
        _json(
            {
                "rate_limits": {
                    "five_hour": {"used_percentage": 0},
                    "seven_day": {"used_percentage": 41, "resets_at": FIXED_RESET},
                }
            }
        ),
        f"Claude         session   0% · resets --        | week  41% · resets {RESET_TEXT}\n",
    ),
    Case(
        "missing-usage-no-invented-rate",
        _json(
            {
                "rate_limits": {
                    "five_hour": {"resets_at": FIXED_RESET},
                    "seven_day": {"used_percentage": 41, "resets_at": FIXED_RESET},
                }
            }
        ),
        f"Claude         session   --                    | week  41% · resets {RESET_TEXT}\n",
    ),
    Case(
        "out-of-range-session-reset-keeps-week",
        _json(
            {
                "rate_limits": {
                    "five_hour": {"used_percentage": 37, "resets_at": 1e18},
                    "seven_day": {"used_percentage": 41, "resets_at": FIXED_RESET},
                }
            }
        ),
        f"Claude         session   --                    | week  41% · resets {RESET_TEXT}\n",
    ),
)


def _src(repo_root: str) -> Path | None:
    root = Path(repo_root).expanduser()
    if not root.is_dir():
        print(f"quota acceptance: repository root is not a directory: {root}", file=sys.stderr)
        return None
    src = root / "src"
    if src.is_symlink():
        print(f"quota acceptance: refusing symlinked src: {src}", file=sys.stderr)
        return None
    package = src / "usage_statusline"
    if package.is_symlink():
        print(f"quota acceptance: refusing symlinked package: {package}", file=sys.stderr)
        return None
    if not src.is_dir() or not (package / "__main__.py").is_file():
        print(f"quota acceptance: no usage_statusline CLI under {src}", file=sys.stderr)
        return None
    return src.resolve()


def _container_command(src: Path) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--interactive",
        "--pull=never",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "65534:65534",
        "--mount",
        f"type=bind,src={src},dst=/candidate/src,readonly",
        "--env",
        "HOME=/nonexistent",
        "--env",
        "TZ=UTC",
        "--env",
        "LC_ALL=C",
        "--env",
        "LANG=C",
        IMAGE,
        "python3",
        "-I",
        "-B",
        "-c",
        CHILD_CODE,
        "/candidate/src",
    ]


def _prepare_container() -> bool:
    try:
        image = subprocess.run(
            ["docker", "image", "inspect", IMAGE], capture_output=True, timeout=TIMEOUT
        )
        if image.returncode != 0:
            subprocess.run(["docker", "pull", IMAGE], check=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"quota acceptance could not prepare the pinned image ({error})", file=sys.stderr)
        return False
    return True


def _host_command(src: Path) -> list[str]:
    return [sys.executable, "-I", "-B", "-c", CHILD_CODE, str(src)]


class _RunnerError(Exception):
    def __init__(self, operation: str, cause: OSError) -> None:
        super().__init__(operation)
        self.operation = operation
        self.cause = cause


def _os_error_detail(error: OSError) -> str:
    number = error.errno
    if type(number) is int and 0 <= number <= 2**31 - 1:
        return errno.errorcode.get(number, f"errno {number}")
    return type(error).__name__


def _run(case: Case, src: Path, container: bool) -> subprocess.CompletedProcess[str]:
    command = _container_command(src) if container else _host_command(src)
    if container:
        try:
            return subprocess.run(
                command,
                input=case.stdin,
                text=True,
                capture_output=True,
                timeout=TIMEOUT,
            )
        except OSError as error:
            raise _RunnerError("container process invocation", error) from None

    try:
        with tempfile.TemporaryDirectory(prefix="quota-acceptance-") as temporary:
            root = Path(temporary)
            home = root / "home"
            work = root / "work"
            home.mkdir()
            work.mkdir()
            env = {
                "HOME": str(home),
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "TZ": "UTC",
                "LC_ALL": "C",
                "LANG": "C",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            }
            try:
                return subprocess.run(
                    command,
                    input=case.stdin,
                    text=True,
                    capture_output=True,
                    timeout=TIMEOUT,
                    cwd=work,
                    env=env,
                )
            except OSError as error:
                raise _RunnerError("host process invocation", error) from None
    except OSError as error:
        raise _RunnerError("host workspace", error) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo_root", help="repository root containing src/usage_statusline")
    parser.add_argument(
        "--controls-only", action="store_true", help="run only the baseline controls"
    )
    parser.add_argument(
        "--container", action="store_true", help="run the candidate CLI in the pinned Docker image"
    )
    args = parser.parse_args(argv)

    src = _src(args.repo_root)
    if src is None:
        return 2
    if args.container:
        if shutil.which("docker") is None:
            print("quota acceptance: --container requires docker on PATH", file=sys.stderr)
            return 2
        if not _prepare_container():
            return 2

    cases = CONTROL_CASES if args.controls_only else FULL_CASES
    mode = "container" if args.container else "local host"
    print(f"quota acceptance: {len(cases)} cases ({mode})")

    failures = []
    for case in cases:
        try:
            completed = _run(case, src, args.container)
        except subprocess.TimeoutExpired:
            print(f"INCONCLUSIVE {case.name}: timed out after {TIMEOUT}s")
            return 2
        except _RunnerError as error:
            print(
                f"INCONCLUSIVE {case.name}: {error.operation} failed "
                f"({_os_error_detail(error.cause)})"
            )
            return 2

        if args.container and completed.returncode in (125, 126, 127):
            print(
                f"INCONCLUSIVE {case.name}: container exit status {completed.returncode}. "
                "The status does not identify the failing process."
            )
            return 2

        problems = []
        if completed.returncode != 0:
            problems.append(f"exit status {completed.returncode}, expected 0")
        if completed.stdout != case.expected_stdout:
            problems.append(f"stdout expected {case.expected_stdout!r}, got {completed.stdout!r}")
        if completed.stderr != "":
            problems.append(f"stderr expected '', got {completed.stderr!r}")
        if problems:
            failures.append(case.name)
            print(f"FAIL {case.name}: {'; '.join(problems)}")
        else:
            print(f"PASS {case.name}")

    if failures:
        print(f"FAILED {len(failures)}/{len(cases)} cases: {', '.join(failures)}")
        return 1
    print(f"OK: {len(cases)} cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
