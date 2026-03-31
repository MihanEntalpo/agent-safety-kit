import sys
from pathlib import Path

import yaml
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agsekit_cli.commands.config_gen import config_gen_command
from agsekit_cli.config import DEFAULT_PORTFORWARD_CONFIG_CHECK_INTERVAL_SEC


def test_config_gen_creates_config_file(tmp_path):
    config_path = tmp_path / "config.yaml"
    project_dir = tmp_path / "project"

    runner = CliRunner()
    user_input = "\n".join(
        [
            "",  # global ssh_keys_folder
            "",  # global systemd_env_folder
            "",  # global portforward interval
            "",  # global http proxy port pool start
            "",  # global http proxy port pool end
            "",  # Имя ВМ (по умолчанию agent-ubuntu)
            "",  # vCPU
            "",  # RAM
            "",  # disk
            "",  # proxychains
            "",  # vm http_proxy mode
            "",  # vm allowed_agents
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
    assert config["global"] == {
        "ssh_keys_folder": None,
        "systemd_env_folder": None,
        "portforward_config_check_interval_sec": DEFAULT_PORTFORWARD_CONFIG_CHECK_INTERVAL_SEC,
        "http_proxy_port_pool": {"start": 48000, "end": 49000},
    }
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
    assert mount["backup_clean_method"] == "thin"
    assert mount["vm"] == "agent-ubuntu"


def test_config_gen_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("AGSEKIT_LANG", "ru")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("original: true\n", encoding="utf-8")

    runner = CliRunner()
    user_input = "\n".join(
        [
            "",  # global ssh_keys_folder
            "",  # global systemd_env_folder
            "",  # global portforward interval
            "",  # global http proxy port pool start
            "",  # global http proxy port pool end
            "",  # Имя ВМ
            "",  # vCPU
            "",  # RAM
            "",  # disk
            "",  # proxychains
            "",  # vm http_proxy mode
            "",  # vm allowed_agents
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


def test_config_gen_writes_agent_proxychains(tmp_path):
    config_path = tmp_path / "config.yaml"
    project_dir = tmp_path / "project"

    runner = CliRunner()
    user_input = "\n".join(
        [
            "",  # global ssh_keys_folder
            "",  # global systemd_env_folder
            "",  # global portforward interval
            "",  # global http proxy port pool start
            "",  # global http proxy port pool end
            "",  # VM name
            "",  # vCPU
            "",  # RAM
            "",  # disk
            "",  # vm proxychains
            "",  # vm http_proxy mode
            "",  # vm allowed_agents
            "",  # cloud-init
            "n",  # add one more VM
            "",  # add mount
            str(project_dir),  # source
            "",  # target
            "",  # backup
            "",  # interval
            "",  # max_backups
            "",  # backup_clean_method
            "",  # mount VM choice
            "n",  # add one more mount
            "y",  # add agent
            "qwen",  # agent name
            "qwen",  # agent type
            "",  # agent vm
            "http://10.0.0.5:3128",  # agent proxychains
            "none",  # agent http_proxy mode
            "n",  # add env var
            "n",  # add one more agent
            "",  # destination
        ]
    ) + "\n"

    result = runner.invoke(
        config_gen_command,
        ["--config", str(config_path), "--overwrite"],
        input=user_input,
    )

    assert result.exit_code == 0
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["agents"]["qwen"]["proxychains"] == "http://10.0.0.5:3128"


def test_config_gen_writes_explicit_empty_agent_proxychains(tmp_path):
    config_path = tmp_path / "config.yaml"
    project_dir = tmp_path / "project"

    runner = CliRunner()
    user_input = "\n".join(
        [
            "",  # global ssh_keys_folder
            "",  # global systemd_env_folder
            "",  # global portforward interval
            "",  # global http proxy port pool start
            "",  # global http proxy port pool end
            "",  # VM name
            "",  # vCPU
            "",  # RAM
            "",  # disk
            "",  # vm proxychains
            "",  # vm http_proxy mode
            "",  # vm allowed_agents
            "",  # cloud-init
            "n",  # add one more VM
            "",  # add mount
            str(project_dir),  # source
            "",  # target
            "",  # backup
            "",  # interval
            "",  # max_backups
            "",  # backup_clean_method
            "",  # mount VM choice
            "n",  # add one more mount
            "y",  # add agent
            "qwen",  # agent name
            "qwen",  # agent type
            "",  # agent vm
            "\"\"",  # agent proxychains: explicit empty string
            "none",  # agent http_proxy mode
            "n",  # add env var
            "n",  # add one more agent
            "",  # destination
        ]
    ) + "\n"

    result = runner.invoke(
        config_gen_command,
        ["--config", str(config_path), "--overwrite"],
        input=user_input,
    )

    assert result.exit_code == 0
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["agents"]["qwen"]["proxychains"] == ""


def test_config_gen_writes_vm_allowed_agents(tmp_path):
    config_path = tmp_path / "config.yaml"
    project_dir = tmp_path / "project"

    runner = CliRunner()
    user_input = "\n".join(
        [
            "",  # global ssh_keys_folder
            "",  # global systemd_env_folder
            "",  # global portforward interval
            "",  # global http proxy port pool start
            "",  # global http proxy port pool end
            "",  # VM name
            "",  # vCPU
            "",  # RAM
            "",  # disk
            "",  # vm proxychains
            "",  # vm http_proxy mode
            "qwen, codex",  # vm allowed_agents
            "",  # cloud-init
            "n",  # add one more VM
            "",  # add mount
            str(project_dir),  # source
            "",  # target
            "",  # backup
            "",  # interval
            "",  # max_backups
            "",  # backup_clean_method
            "",  # mount VM choice
            "n",  # add one more mount
            "n",  # add agent
            "",  # destination
        ]
    ) + "\n"

    result = runner.invoke(
        config_gen_command,
        ["--config", str(config_path), "--overwrite"],
        input=user_input,
    )

    assert result.exit_code == 0
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["vms"]["agent-ubuntu"]["allowed_agents"] == ["qwen", "codex"]


def test_config_gen_prompts_and_writes_custom_global_settings(tmp_path):
    config_path = tmp_path / "config.yaml"
    ssh_dir = tmp_path / "custom-ssh"
    env_dir = tmp_path / "custom-env"

    runner = CliRunner()
    user_input = "\n".join(
        [
            str(ssh_dir),  # global ssh_keys_folder
            str(env_dir),  # global systemd_env_folder
            "21",  # global portforward interval
            "48100",  # global http proxy port pool start
            "48200",  # global http proxy port pool end
            "",  # VM name
            "",  # vCPU
            "",  # RAM
            "",  # disk
            "",  # vm proxychains
            "",  # vm http_proxy mode
            "",  # vm allowed_agents
            "",  # cloud-init
            "n",  # add one more VM
            "n",  # add mount
            "n",  # add agent
            "",  # destination
        ]
    ) + "\n"

    result = runner.invoke(
        config_gen_command,
        ["--config", str(config_path), "--overwrite"],
        input=user_input,
    )

    assert result.exit_code == 0
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["global"] == {
        "ssh_keys_folder": str(ssh_dir),
        "systemd_env_folder": str(env_dir),
        "portforward_config_check_interval_sec": 21,
        "http_proxy_port_pool": {"start": 48100, "end": 48200},
    }
