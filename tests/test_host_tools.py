import subprocess

import agsekit_cli.host_tools as host_tools


def test_host_tool_command_prefers_plain_name_when_available_in_path(monkeypatch):
    monkeypatch.setattr(host_tools.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(host_tools.platform, "system", lambda: "Windows")

    assert host_tools.multipass_command() == "multipass"
    assert host_tools.rsync_command() == "rsync"


def test_host_tool_command_falls_back_to_windows_standard_path(monkeypatch, tmp_path):
    multipass_exe = tmp_path / "Multipass" / "bin" / "multipass.exe"
    msys_bin = tmp_path / "msys64" / "usr" / "bin"
    rsync_exe = msys_bin / "rsync.exe"
    ssh_exe = msys_bin / "ssh.exe"

    multipass_exe.parent.mkdir(parents=True)
    msys_bin.mkdir(parents=True)
    multipass_exe.write_text("", encoding="utf-8")
    rsync_exe.write_text("", encoding="utf-8")
    ssh_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(host_tools.shutil, "which", lambda _name: None)
    monkeypatch.setattr(host_tools.platform, "system", lambda: "Windows")
    monkeypatch.setenv("AGSEKIT_MULTIPASS_EXE", str(multipass_exe))
    monkeypatch.setenv("AGSEKIT_MSYS2_ROOT", str(tmp_path / "msys64"))

    assert host_tools.multipass_command() == str(multipass_exe)
    assert host_tools.rsync_command() == str(rsync_exe)
    assert host_tools.ssh_command() == str(ssh_exe)


def test_host_tool_command_keeps_plain_name_when_missing(monkeypatch):
    monkeypatch.setattr(host_tools.shutil, "which", lambda _name: None)
    monkeypatch.setattr(host_tools.platform, "system", lambda: "Linux")

    assert host_tools.multipass_command() == "multipass"
    assert host_tools.host_tool_exists("multipass") is False


def test_run_multipass_subprocess_decodes_windows_output(monkeypatch):
    monkeypatch.setattr(host_tools.platform, "system", lambda: "Windows")
    monkeypatch.setattr(host_tools, "windows_output_encodings", lambda: ("cp866",))

    def fake_run(command, check=False, capture_output=False, text=False):
        del check, capture_output, text
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="Не удалось запустить виртуальную машину".encode("cp866"),
        )

    monkeypatch.setattr(host_tools.subprocess, "run", fake_run)

    result = host_tools.run_multipass_subprocess(["multipass", "launch"], check=False, capture_output=True)

    assert result.stderr == "Не удалось запустить виртуальную машину"


def test_run_multipass_subprocess_uses_plain_text_mode_outside_windows(monkeypatch):
    monkeypatch.setattr(host_tools.platform, "system", lambda: "Linux")

    def fake_run(command, check=False, capture_output=False, text=True):
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(host_tools.subprocess, "run", fake_run)

    result = host_tools.run_multipass_subprocess(["multipass", "list"], check=False, capture_output=True)

    assert result.stdout == "ok"
