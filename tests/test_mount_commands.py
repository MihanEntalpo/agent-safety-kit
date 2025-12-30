import sys
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.mounts as mount_commands


def _write_config(path: Path, mounts: list[str]) -> None:
    mounts_yaml = "\n".join(mounts)
    path.write_text(
        f"""
vms:
  agent:
    cpu: 1
    ram: 1G
    disk: 5G
mounts:
{mounts_yaml}
""",
        encoding="utf-8",
    )


def test_mount_command_uses_config(monkeypatch, tmp_path):
    mount_source = tmp_path / "data"
    target = "/home/ubuntu/data"
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [
            f"  - source: {mount_source}",
            f"    target: {target}",
            "    vm: agent",
        ],
    )

    calls = []

    def fake_mount(mount):
        calls.append((mount.source, mount.target, mount.vm_name))

    monkeypatch.setattr(mount_commands, "mount_directory", fake_mount)

    runner = CliRunner()
    result = runner.invoke(
        mount_commands.mount_command,
        ["--source-dir", str(mount_source), "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls == [(mount_source.resolve(), Path(target), "agent")]
    assert "Mounted" in result.output


def test_mount_command_all_mounts(monkeypatch, tmp_path):
    first = tmp_path / "one"
    second = tmp_path / "two"
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [
            f"  - source: {first}",
            "    target: /home/ubuntu/one",
            f"  - source: {second}",
            "    target: /home/ubuntu/two",
        ],
    )

    calls = []

    def fake_mount(mount):
        calls.append(mount.source)

    monkeypatch.setattr(mount_commands, "mount_directory", fake_mount)

    runner = CliRunner()
    result = runner.invoke(mount_commands.mount_command, ["--all", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [first.resolve(), second.resolve()]
    assert "Mounted" in result.output


def test_mount_command_defaults_to_single_mount(monkeypatch, tmp_path):
    mount_source = tmp_path / "data"
    target = "/home/ubuntu/data"
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [
            f"  - source: {mount_source}",
            f"    target: {target}",
            "    vm: agent",
        ],
    )

    calls = []

    def fake_mount(mount):
        calls.append((mount.source, mount.target, mount.vm_name))

    monkeypatch.setattr(mount_commands, "mount_directory", fake_mount)

    runner = CliRunner()
    result = runner.invoke(mount_commands.mount_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [(mount_source.resolve(), Path(target), "agent")]
    assert "Mounted" in result.output


def test_umount_uses_env_config(monkeypatch, tmp_path):
    mount_source = tmp_path / "data"
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [
            f"  - source: {mount_source}",
            "    target: /home/ubuntu/data",
            "    vm: agent",
        ],
    )

    calls = []

    def fake_umount(mount):
        calls.append((mount.vm_name, mount.target))

    monkeypatch.setattr(mount_commands, "umount_directory", fake_umount)

    runner = CliRunner()
    result = runner.invoke(
        mount_commands.umount_command,
        ["--all"],
        env={"CONFIG_PATH": str(config_path)},
    )

    assert result.exit_code == 0
    assert calls == [("agent", Path("/home/ubuntu/data"))]
    assert "Unmounted" in result.output


def test_umount_defaults_to_single_mount(monkeypatch, tmp_path):
    mount_source = tmp_path / "data"
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [
            f"  - source: {mount_source}",
            "    target: /home/ubuntu/data",
            "    vm: agent",
        ],
    )

    calls = []

    def fake_umount(mount):
        calls.append((mount.vm_name, mount.target))

    monkeypatch.setattr(mount_commands, "umount_directory", fake_umount)

    runner = CliRunner()
    result = runner.invoke(mount_commands.umount_command, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert calls == [("agent", Path("/home/ubuntu/data"))]
    assert "Unmounted" in result.output


def test_mount_command_requires_selector_when_multiple(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [
            "  - source: /data",
            "    target: /home/ubuntu/data",
            "  - source: /other",
            "    target: /home/ubuntu/other",
        ],
    )

    runner = CliRunner()
    result = runner.invoke(mount_commands.mount_command, ["--config", str(config_path)])

    assert result.exit_code != 0
    assert "--all" in result.output
