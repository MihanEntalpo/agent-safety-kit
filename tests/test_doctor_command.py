import sys
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.commands.doctor as doctor_module
from agsekit_cli.commands.doctor import doctor_command


def _write_config(config_path: Path, source_dir: Path) -> None:
    config_path.write_text(
        f"""
vms:
  agent:
    cpu: 1
    ram: 1G
    disk: 5G
mounts:
  - source: {source_dir}
    target: /home/ubuntu/project
    vm: agent
""",
        encoding="utf-8",
    )


def test_doctor_restarts_multipass_and_repairs_broken_mount(monkeypatch, tmp_path):
    source_dir = tmp_path / "project"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("hello", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source_dir)

    monkeypatch.setattr(doctor_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        doctor_module,
        "fetch_existing_info",
        lambda: '{"list":[{"name":"agent","state":"Running"}]}',
    )
    monkeypatch.setattr(
        doctor_module,
        "load_multipass_mounts",
        lambda **_kwargs: {
            "agent": {(source_dir.resolve(), Path("/home/ubuntu/project"))},
        },
    )
    vm_checks = iter([False, True])
    monkeypatch.setattr(doctor_module, "vm_path_has_entries", lambda *_args, **_kwargs: next(vm_checks))
    restart_calls: list[str] = []
    monkeypatch.setattr(doctor_module, "_restart_multipass", lambda **_kwargs: restart_calls.append("restart"))

    runner = CliRunner()
    result = runner.invoke(
        doctor_command,
        ["--config", str(config_path)],
        input="y\n",
        env={"AGSEKIT_LANG": "en"},
    )

    assert result.exit_code == 0
    assert restart_calls == ["restart"]
    assert "Restart Multipass now?" in result.output
    assert "Running sudo snap restart multipass..." in result.output
    assert "Doctor repaired all detected issues." in result.output


def test_doctor_reports_healthy_mounts_without_restart(monkeypatch, tmp_path):
    source_dir = tmp_path / "project"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("hello", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source_dir)

    monkeypatch.setattr(doctor_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        doctor_module,
        "fetch_existing_info",
        lambda: '{"list":[{"name":"agent","state":"Running"}]}',
    )
    monkeypatch.setattr(
        doctor_module,
        "load_multipass_mounts",
        lambda **_kwargs: {
            "agent": {(source_dir.resolve(), Path("/home/ubuntu/project"))},
        },
    )
    monkeypatch.setattr(doctor_module, "vm_path_has_entries", lambda *_args, **_kwargs: True)
    restart_calls: list[str] = []
    monkeypatch.setattr(doctor_module, "_restart_multipass", lambda **_kwargs: restart_calls.append("restart"))

    runner = CliRunner()
    result = runner.invoke(doctor_command, ["--config", str(config_path)], env={"AGSEKIT_LANG": "en"})

    assert result.exit_code == 0
    assert not restart_calls
    assert "No known issues detected." in result.output


def test_doctor_fails_when_mount_stays_broken_after_restart(monkeypatch, tmp_path):
    source_dir = tmp_path / "project"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("hello", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source_dir)

    monkeypatch.setattr(doctor_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        doctor_module,
        "fetch_existing_info",
        lambda: '{"list":[{"name":"agent","state":"Running"}]}',
    )
    monkeypatch.setattr(
        doctor_module,
        "load_multipass_mounts",
        lambda **_kwargs: {
            "agent": {(source_dir.resolve(), Path("/home/ubuntu/project"))},
        },
    )
    monkeypatch.setattr(doctor_module, "vm_path_has_entries", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(doctor_module, "_restart_multipass", lambda **_kwargs: None)

    runner = CliRunner()
    result = runner.invoke(
        doctor_command,
        ["--config", str(config_path), "-y"],
        env={"AGSEKIT_LANG": "en"},
    )

    assert result.exit_code != 0
    assert "Doctor could not repair 1 issue(s)." in result.output


def test_doctor_skips_configured_mounts_that_are_not_mounted(monkeypatch, tmp_path):
    source_dir = tmp_path / "project"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("hello", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source_dir)

    monkeypatch.setattr(doctor_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        doctor_module,
        "fetch_existing_info",
        lambda: '{"list":[{"name":"agent","state":"Running"}]}',
    )
    monkeypatch.setattr(doctor_module, "load_multipass_mounts", lambda **_kwargs: {"agent": set()})
    restart_calls: list[str] = []
    monkeypatch.setattr(doctor_module, "_restart_multipass", lambda **_kwargs: restart_calls.append("restart"))

    runner = CliRunner()
    result = runner.invoke(doctor_command, ["--config", str(config_path)], env={"AGSEKIT_LANG": "en"})

    assert result.exit_code == 0
    assert "is not currently mounted in Multipass" in result.output
    assert "No known issues detected." in result.output
    assert not restart_calls


def test_doctor_can_cancel_repair_after_prompt(monkeypatch, tmp_path):
    source_dir = tmp_path / "project"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("hello", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source_dir)

    monkeypatch.setattr(doctor_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        doctor_module,
        "fetch_existing_info",
        lambda: '{"list":[{"name":"agent","state":"Running"}]}',
    )
    monkeypatch.setattr(
        doctor_module,
        "load_multipass_mounts",
        lambda **_kwargs: {
            "agent": {(source_dir.resolve(), Path("/home/ubuntu/project"))},
        },
    )
    monkeypatch.setattr(doctor_module, "vm_path_has_entries", lambda *_args, **_kwargs: False)
    restart_calls: list[str] = []
    monkeypatch.setattr(doctor_module, "_restart_multipass", lambda **_kwargs: restart_calls.append("restart"))

    runner = CliRunner()
    result = runner.invoke(
        doctor_command,
        ["--config", str(config_path)],
        input="n\n",
        env={"AGSEKIT_LANG": "en"},
    )

    assert result.exit_code == 0
    assert "Doctor repair cancelled." in result.output
    assert not restart_calls


def test_doctor_requires_yes_in_non_interactive_mode(monkeypatch, tmp_path):
    source_dir = tmp_path / "project"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("hello", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, source_dir)

    monkeypatch.setattr(doctor_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        doctor_module,
        "fetch_existing_info",
        lambda: '{"list":[{"name":"agent","state":"Running"}]}',
    )
    monkeypatch.setattr(
        doctor_module,
        "load_multipass_mounts",
        lambda **_kwargs: {
            "agent": {(source_dir.resolve(), Path("/home/ubuntu/project"))},
        },
    )
    monkeypatch.setattr(doctor_module, "vm_path_has_entries", lambda *_args, **_kwargs: False)
    restart_calls: list[str] = []
    monkeypatch.setattr(doctor_module, "_restart_multipass", lambda **_kwargs: restart_calls.append("restart"))

    runner = CliRunner()
    result = runner.invoke(
        doctor_command,
        ["--config", str(config_path), "--non-interactive"],
        env={"AGSEKIT_LANG": "en"},
    )

    assert result.exit_code != 0
    assert "Re-run with -y in non-interactive mode." in result.output
    assert not restart_calls
