import errno
import importlib.util
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quota_acceptance.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("quota_acceptance_under_test", CHECKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_checker(monkeypatch, capsys, tmp_path, outcomes, container):
    checker = _load_checker()
    package = tmp_path / "src" / "usage_statusline"
    package.mkdir(parents=True)
    (package / "__main__.py").touch()
    calls = []
    if container:
        monkeypatch.setattr(checker.shutil, "which", lambda name: "/usr/bin/docker")
        monkeypatch.setattr(checker, "_prepare_container", lambda: True)

    def fake_run(command, **kwargs):
        index = len(calls)
        calls.append(command)
        outcome = outcomes.get(index, 0)
        if isinstance(outcome, Exception):
            raise outcome
        case = checker.CONTROL_CASES[index]
        stderr = "untrusted runner message" if container and outcome in (125, 126, 127) else ""
        return subprocess.CompletedProcess(command, outcome, case.expected_stdout, stderr)

    monkeypatch.setattr(checker.subprocess, "run", fake_run)
    args = [str(tmp_path), "--controls-only"]
    if container:
        args.append("--container")
    status = checker.main(args)
    streams = capsys.readouterr()
    names = [case.name for case in checker.CONTROL_CASES]
    return status, streams.out + streams.err, names, len(calls)


@pytest.mark.parametrize(
    ("container", "status"),
    [
        (False, 0),
        (True, 0),
        (False, 125),
        (False, 126),
        (False, 127),
        (True, 1),
        (True, 2),
        (False, 1),
    ],
)
def test_evaluated_candidate_uses_normal_exit_contract(
    monkeypatch, capsys, tmp_path, container, status
):
    exit_code, output, names, calls = _run_checker(
        monkeypatch, capsys, tmp_path, {1: status}, container
    )
    assert calls == len(names)
    assert "INCONCLUSIVE" not in output
    if status:
        assert exit_code == 1
        assert f"FAIL {names[1]}" in output
        assert f"exit status {status}, expected 0" in output
    else:
        assert exit_code == 0
        assert f"OK: {len(names)} cases passed" in output


@pytest.mark.parametrize(
    ("container", "problem", "reason"),
    [
        (True, 125, "container exit status 125"),
        (True, 126, "container exit status 126"),
        (True, 127, "container exit status 127"),
        (False, subprocess.TimeoutExpired(cmd=["python3"], timeout=20), "timed out"),
        (True, subprocess.TimeoutExpired(cmd=["docker"], timeout=20), "timed out"),
        (False, OSError("untrusted runner message"), "host process"),
        (True, OSError("untrusted runner message"), "container process"),
        (
            False,
            PermissionError(errno.EACCES, "untrusted runner message", "/synthetic/private-path"),
            "host process",
        ),
        (
            True,
            FileNotFoundError(errno.ENOENT, "untrusted runner message", "/synthetic/private-path"),
            "container process",
        ),
    ],
)
def test_inconclusive_stops_after_current_case(
    monkeypatch, capsys, tmp_path, container, problem, reason
):
    status, output, names, calls = _run_checker(
        monkeypatch, capsys, tmp_path, {1: problem}, container
    )
    assert status == 2
    assert calls == 2
    assert f"PASS {names[0]}" in output
    diagnostic = next(
        row for row in output.splitlines() if row.startswith(f"INCONCLUSIVE {names[1]}")
    )
    assert reason in diagnostic
    assert f"FAIL {names[1]}" not in output
    assert "untrusted runner message" not in output
    assert "/synthetic/private-path" not in output
    if isinstance(problem, OSError):
        assert errno.errorcode.get(problem.errno, type(problem).__name__) in diagnostic


@pytest.mark.parametrize("cleanup", [False, True], ids=["creation", "cleanup"])
def test_host_workspace_error_describes_operation_without_private_details(
    monkeypatch, capsys, tmp_path, cleanup
):
    real_workspace = tempfile.TemporaryDirectory
    error = PermissionError(errno.EACCES, "untrusted runner message", "/synthetic/private-path")

    @contextmanager
    def failed_workspace(**kwargs):
        if cleanup:
            with real_workspace(**kwargs) as path:
                yield path
        raise error

    monkeypatch.setattr(tempfile, "TemporaryDirectory", failed_workspace)
    status, output, names, calls = _run_checker(monkeypatch, capsys, tmp_path, {}, False)
    assert status == 2
    assert calls == int(cleanup)
    diagnostic = next(
        row for row in output.splitlines() if row.startswith(f"INCONCLUSIVE {names[0]}")
    )
    assert "host workspace" in diagnostic and "EACCES" in diagnostic
    assert "/synthetic/private-path" not in output
    assert "untrusted runner message" not in output


def test_inconclusive_preserves_prior_failure_evidence(monkeypatch, capsys, tmp_path):
    status, output, names, calls = _run_checker(monkeypatch, capsys, tmp_path, {0: 1, 1: 125}, True)
    assert status == 2
    assert calls == 2
    assert f"FAIL {names[0]}" in output
    assert f"INCONCLUSIVE {names[1]}" in output
    assert "FAILED" not in output
