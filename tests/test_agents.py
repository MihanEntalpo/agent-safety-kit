from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.agents as agents


def test_run_in_vm_uses_cd_and_no_workdir_flag(monkeypatch):
    calls = {}

    def fake_run(args, check):
        calls["args"] = args

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(agents, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(agents.subprocess, "run", fake_run)

    workdir = Path("/home/ubuntu/project")
    env_vars = {"TOKEN": "abc"}

    exit_code = agents.run_in_vm("agent-vm", workdir, ["qwen", "--flag"], env_vars)

    assert exit_code == 0
    args = calls["args"]
    assert args[:3] == ["multipass", "exec", "agent-vm"]
    assert "--workdir" not in args
    assert args[-1].startswith("export NVM_DIR=")
    assert f"cd {workdir}" in args[-1]
    assert "qwen --flag" in args[-1]
