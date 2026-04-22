from click.testing import CliRunner

from agsekit_cli.commands import pip_upgrade as pip_upgrade_module


def _result(returncode: int = 0, stdout: str = "", stderr: str = ""):
    class Result:
        def __init__(self) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    return Result()


def test_pip_upgrade_reports_updated_versions(monkeypatch):
    monkeypatch.setattr(pip_upgrade_module, "_detect_env_path", lambda: "/tmp/venv")
    monkeypatch.setattr(pip_upgrade_module, "_is_windows", lambda: False)

    calls = {"show_count": 0}

    def fake_run(command, check=False, capture_output=False, text=False):
        del check, capture_output, text
        if command[-2:] == ["show", "agsekit"]:
            calls["show_count"] += 1
            if calls["show_count"] == 1:
                return _result(stdout="Name: agsekit\nVersion: 1.0.0\n")
            return _result(stdout="Name: agsekit\nVersion: 1.1.0\n")
        if command[-3:] == ["install", "agsekit", "--upgrade"]:
            return _result()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(pip_upgrade_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(pip_upgrade_module.pip_upgrade_command, [], env={"AGSEKIT_LANG": "en"})

    assert result.exit_code == 0
    assert "Using Python environment: /tmp/venv" in result.output
    assert "Upgrading agsekit with pip..." in result.output
    assert "agsekit has been upgraded from version 1.0.0 to version 1.1.0." in result.output


def test_pip_upgrade_reports_already_latest(monkeypatch):
    monkeypatch.setattr(pip_upgrade_module, "_detect_env_path", lambda: "/tmp/venv")
    monkeypatch.setattr(pip_upgrade_module, "_is_windows", lambda: False)

    calls = {"show_count": 0}

    def fake_run(command, check=False, capture_output=False, text=False):
        del check, capture_output, text
        if command[-2:] == ["show", "agsekit"]:
            calls["show_count"] += 1
            return _result(stdout="Name: agsekit\nVersion: 1.1.0\n")
        if command[-3:] == ["install", "agsekit", "--upgrade"]:
            return _result()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(pip_upgrade_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(pip_upgrade_module.pip_upgrade_command, [], env={"AGSEKIT_LANG": "en"})

    assert result.exit_code == 0
    assert "Upgrading agsekit with pip..." in result.output
    assert "agsekit is already at the latest version: 1.1.0." in result.output


def test_pip_upgrade_not_installed(monkeypatch):
    monkeypatch.setattr(pip_upgrade_module, "_detect_env_path", lambda: "/tmp/venv")
    monkeypatch.setattr(pip_upgrade_module, "_is_windows", lambda: False)

    def fake_run(command, check=False, capture_output=False, text=False):
        del check, capture_output, text
        if command[-2:] == ["show", "agsekit"]:
            return _result(returncode=1)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(pip_upgrade_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(pip_upgrade_module.pip_upgrade_command, [], env={"AGSEKIT_LANG": "en"})

    assert result.exit_code != 0
    assert "Cannot upgrade agsekit because it is not installed in this environment via pip." in result.output


def test_pip_upgrade_windows_reexecs_under_python_before_install(monkeypatch):
    monkeypatch.setattr(pip_upgrade_module, "_detect_env_path", lambda: r"C:\Users\natalia\.local\share\agsekit\venv")
    monkeypatch.setattr(pip_upgrade_module, "_is_windows", lambda: True)
    monkeypatch.setattr(pip_upgrade_module.sys, "executable", r"C:\Users\natalia\.local\share\agsekit\venv\Scripts\python.exe")

    def fake_run(command, check=False, capture_output=False, text=False):
        del check, capture_output, text
        if command[-2:] == ["show", "agsekit"]:
            return _result(stdout="Name: agsekit\nVersion: 1.5.16\n")
        raise AssertionError(f"Unexpected command: {command}")

    execv_call = {}

    def fake_execv(executable, args):
        execv_call["executable"] = executable
        execv_call["args"] = args
        raise SystemExit(0)

    monkeypatch.setattr(pip_upgrade_module.subprocess, "run", fake_run)
    monkeypatch.setattr(pip_upgrade_module.os, "execv", fake_execv)

    runner = CliRunner()
    result = runner.invoke(pip_upgrade_module.pip_upgrade_command, [], env={"AGSEKIT_LANG": "en"})

    assert result.exit_code == 0
    assert r"Using Python environment: C:\Users\natalia\.local\share\agsekit\venv" in result.output
    assert execv_call["executable"] == r"C:\Users\natalia\.local\share\agsekit\venv\Scripts\python.exe"
    assert execv_call["args"][:2] == [
        r"C:\Users\natalia\.local\share\agsekit\venv\Scripts\python.exe",
        "-c",
    ]
    assert '"install", "agsekit", "--upgrade"' in execv_call["args"][2]
    assert '"show", "agsekit"' in execv_call["args"][2]
