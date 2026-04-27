import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.debug as debug_module


class _FixedDateTime:
    @classmethod
    def now(cls):
        return datetime(2026, 4, 27, 14, 15, 16, 789000)


def test_debug_log_command_adds_timestamp(monkeypatch, capsys):
    monkeypatch.setattr(debug_module, "datetime", _FixedDateTime)

    debug_module.debug_log_command(["echo", "hello"], enabled=True)

    output = capsys.readouterr().out.strip()
    assert output == "[DEBUG] 2026-04-27 14:15:16.789 command: echo hello"


def test_debug_log_result_adds_timestamp(monkeypatch, capsys):
    class Result:
        returncode = 0
        stdout = "done"
        stderr = "warn"

    monkeypatch.setattr(debug_module, "datetime", _FixedDateTime)

    debug_module.debug_log_result(Result(), enabled=True)

    output = capsys.readouterr().out
    assert re.search(r"^\[DEBUG\] 2026-04-27 14:15:16\.789 exit code: 0$", output, re.MULTILINE)
    assert re.search(r"^\[DEBUG\] 2026-04-27 14:15:16\.789 stdout:$", output, re.MULTILINE)
    assert re.search(r"^\[DEBUG\] 2026-04-27 14:15:16\.789 stderr:$", output, re.MULTILINE)
