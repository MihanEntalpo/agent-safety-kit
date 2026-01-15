import sys
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.removemount as removemount_commands


def _write_config(path: Path, mounts: list[str], vms: list[str] | None = None) -> None:
    vms = vms or ["agent"]
    vms_yaml = "\n".join([f"  {name}:\n    cpu: 1\n    ram: 1G\n    disk: 5G" for name in vms])
    mounts_yaml = "\n".join(mounts)
    path.write_text(
        f"""
vms:
{vms_yaml}
mounts:
{mounts_yaml}
""",
        encoding="utf-8",
    )


def _read_config_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_removemount_removes_entry_and_creates_backup(monkeypatch, tmp_path):
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

    def fake_umount(mount):
        calls.append((mount.vm_name, mount.target))

    monkeypatch.setattr(removemount_commands, "umount_directory", fake_umount)

    runner = CliRunner()
    result = runner.invoke(
        removemount_commands.removemount_command,
        [str(first), "--config", str(config_path), "-y"],
    )

    assert result.exit_code == 0
    assert calls == [("agent", Path("/home/ubuntu/one"))]
    config_text = _read_config_text(config_path)
    assert f"source: {second}" in config_text
    assert f"source: {first}" not in config_text
    backups = list(tmp_path.glob("config-backup-*.yaml"))
    assert backups


def test_removemount_requires_vm_when_duplicate_sources(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [
            "  - source: /data",
            "    target: /home/ubuntu/data",
            "    vm: primary",
            "  - source: /data",
            "    target: /home/ubuntu/data2",
            "    vm: secondary",
        ],
        vms=["primary", "secondary"],
    )

    monkeypatch.setattr(removemount_commands, "umount_directory", lambda _: None)
    runner = CliRunner()
    result = runner.invoke(
        removemount_commands.removemount_command,
        ["/data", "--config", str(config_path), "-y"],
    )

    assert result.exit_code != 0
    assert "--vm" in result.output


def test_removemount_with_vm_selects_entry(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [
            "  - source: /data",
            "    target: /home/ubuntu/data",
            "    vm: primary",
            "  - source: /data",
            "    target: /home/ubuntu/data2",
            "    vm: secondary",
        ],
        vms=["primary", "secondary"],
    )

    calls = []

    def fake_umount(mount):
        calls.append((mount.vm_name, mount.target))

    monkeypatch.setattr(removemount_commands, "umount_directory", fake_umount)

    runner = CliRunner()
    result = runner.invoke(
        removemount_commands.removemount_command,
        ["/data", "--vm", "secondary", "--config", str(config_path), "-y"],
    )

    assert result.exit_code == 0
    assert calls == [("secondary", Path("/home/ubuntu/data2"))]
    config_text = _read_config_text(config_path)
    assert "vm: primary" in config_text
    assert "vm: secondary" not in config_text


def test_removemount_keeps_config_when_umount_fails(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        [
            "  - source: /data",
            "    target: /home/ubuntu/data",
            "    vm: agent",
        ],
    )

    def failing_umount(_mount):
        raise removemount_commands.MultipassError("boom")

    monkeypatch.setattr(removemount_commands, "umount_directory", failing_umount)

    runner = CliRunner()
    result = runner.invoke(
        removemount_commands.removemount_command,
        ["/data", "--config", str(config_path), "-y"],
    )

    assert result.exit_code != 0
    config_text = _read_config_text(config_path)
    assert "source: /data" in config_text
