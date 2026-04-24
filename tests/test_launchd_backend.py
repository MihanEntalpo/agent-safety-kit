import plistlib
import subprocess
from pathlib import Path

from agsekit_cli.daemon_backends import LAUNCHD_LABEL, LaunchdDaemonBackend


def test_launchd_install_writes_plist_and_uses_expected_commands(monkeypatch, tmp_path):
    backend = LaunchdDaemonBackend()
    launch_agents_dir = tmp_path / "LaunchAgents"
    logs_dir = tmp_path / "Logs" / "agsekit"
    config_path = tmp_path / "config.yaml"
    config_path.write_text("vms: {}\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(LaunchdDaemonBackend, "launch_agents_dir", property(lambda self: launch_agents_dir))
    monkeypatch.setattr(LaunchdDaemonBackend, "logs_dir", property(lambda self: logs_dir))
    monkeypatch.setattr(backend, "_resolve_agsekit_bin", lambda: Path("/opt/agsekit/bin/agsekit"))
    monkeypatch.setattr(backend, "_run_launchctl", lambda command, announce=True, check=True: calls.append((command, announce, check)) or subprocess.CompletedProcess(command, 0, stdout="", stderr=""))

    backend.install(config_path, project_dir=tmp_path / "project", announce=False)

    plist_path = launch_agents_dir / f"{LAUNCHD_LABEL}.plist"
    assert plist_path.exists()
    plist_data = plistlib.loads(plist_path.read_bytes())
    assert plist_data["Label"] == LAUNCHD_LABEL
    assert plist_data["ProgramArguments"] == ["/opt/agsekit/bin/agsekit", "portforward", "--config", str(config_path.resolve())]
    assert plist_data["StandardOutPath"] == str(logs_dir / "daemon.stdout.log")
    assert plist_data["StandardErrorPath"] == str(logs_dir / "daemon.stderr.log")
    assert calls == [
        (["launchctl", "bootout", backend.domain_target, str(plist_path)], False, False),
        (["launchctl", "bootstrap", backend.domain_target, str(plist_path)], False, True),
        (["launchctl", "enable", backend.job_target], False, True),
        (["launchctl", "kickstart", "-k", backend.job_target], False, True),
    ]


def test_launchd_status_lines_include_log_paths_and_tails(monkeypatch, tmp_path):
    backend = LaunchdDaemonBackend()
    launch_agents_dir = tmp_path / "LaunchAgents"
    logs_dir = tmp_path / "Logs" / "agsekit"
    plist_path = launch_agents_dir / f"{LAUNCHD_LABEL}.plist"
    launch_agents_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)
    plist_path.write_text("plist", encoding="utf-8")
    (logs_dir / "daemon.stdout.log").write_text("one\ntwo\n", encoding="utf-8")
    (logs_dir / "daemon.stderr.log").write_text("err1\n", encoding="utf-8")

    monkeypatch.setattr(LaunchdDaemonBackend, "launch_agents_dir", property(lambda self: launch_agents_dir))
    monkeypatch.setattr(LaunchdDaemonBackend, "logs_dir", property(lambda self: logs_dir))

    def fake_query(command):
        if command[:2] == ["launchctl", "print-disabled"]:
            return subprocess.CompletedProcess(command, 0, stdout='"org.agsekit.portforward" => false\n', stderr="")
        return subprocess.CompletedProcess(command, 0, stdout='state = running\npid = 123\nlast exit code = 0\n', stderr="")

    monkeypatch.setattr(backend, "_query_launchctl", fake_query)

    lines = backend.status_lines()

    assert any("org.agsekit.portforward" in line for line in lines)
    assert any(str(logs_dir / "daemon.stdout.log") in line for line in lines)
    assert any("two" in line for line in lines)
    assert any("err1" in line for line in lines)
