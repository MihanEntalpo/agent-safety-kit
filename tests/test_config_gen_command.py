import sys
from pathlib import Path

import yaml
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agsekit_cli.commands.config_gen import config_gen_command


def test_config_gen_creates_config_file(tmp_path):
    config_path = tmp_path / "config.yaml"
    project_dir = tmp_path / "project"

    runner = CliRunner()
    user_input = "\n".join(
        [
            "",  # Имя ВМ (по умолчанию agent-ubuntu)
            "",  # vCPU
            "",  # RAM
            "",  # disk
            "",  # proxychains
            "",  # cloud-init
            "n",  # добавить ещё ВМ
            "",  # подтвердить добавление монтирования
            str(project_dir),  # source
            "",  # target
            "",  # backup
            "",  # interval
            "",  # max_backups
            "",  # backup_clean_method
            "",  # vm choice
            "n",  # добавить ещё монтирование
            "n",  # добавить агента
            "",  # путь для сохранения (по умолчанию --config)
        ]
    ) + "\n"

    result = runner.invoke(
        config_gen_command,
        ["--config", str(config_path), "--overwrite"],
        input=user_input,
    )

    assert result.exit_code == 0
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    vm = config["vms"]["agent-ubuntu"]
    assert vm["cpu"] == 2
    assert vm["ram"] == "4G"
    assert vm["disk"] == "20G"
    assert vm["cloud-init"] == {}
    assert "proxychains" not in vm

    mount = config["mounts"][0]
    assert mount["source"] == str(project_dir)
    assert mount["target"] == f"/home/ubuntu/{project_dir.name}"
    assert mount["backup"] == str(project_dir.parent / f"backups-{project_dir.name}")
    assert mount["interval"] == 5
    assert mount["max_backups"] == 100
    assert mount["backup_clean_method"] == "tail"
    assert mount["vm"] == "agent-ubuntu"


def test_config_gen_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("AGSEKIT_LANG", "ru")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("original: true\n", encoding="utf-8")

    runner = CliRunner()
    user_input = "\n".join(
        [
            "",  # Имя ВМ
            "",  # vCPU
            "",  # RAM
            "",  # disk
            "",  # proxychains
            "",  # cloud-init
            "n",  # добавить ещё ВМ
            "n",  # не добавлять монтирования
            "n",  # добавить агента
            "",  # путь сохранения
        ]
    ) + "\n"

    result = runner.invoke(
        config_gen_command,
        ["--config", str(config_path)],
        input=user_input,
    )

    assert result.exit_code == 0
    assert "уже существует" in result.output
    assert config_path.read_text(encoding="utf-8") == "original: true\n"
