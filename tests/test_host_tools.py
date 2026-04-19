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
