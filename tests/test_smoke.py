import io
import json

import pytest

from usage_statusline import main as m


def test_main_prints_two_lines(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(m, "antigravity_line", lambda: "Antigravity  x")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({})))
    m.main()
    assert capsys.readouterr().out.splitlines()[1] == "Antigravity  x"


def test_main_tolerates_bad_stdin(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(m, "antigravity_line", lambda: "Antigravity  x")
    monkeypatch.setattr("sys.stdin", io.StringIO("garbage"))
    m.main()
    assert capsys.readouterr().out.startswith("Claude")
