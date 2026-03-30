import pytest

from agsekit_cli.config import (
    ConfigError,
    DEFAULT_PORTFORWARD_CONFIG_CHECK_INTERVAL_SEC,
    DEFAULT_SSH_KEYS_DIR,
    DEFAULT_SYSTEMD_ENV_DIR,
    load_global_config,
)


def test_load_global_config_returns_defaults_when_section_missing():
    config = {"vms": {"agent": {"cpu": 2, "ram": "2G", "disk": "10G"}}}

    global_config = load_global_config(config)

    assert global_config.ssh_keys_folder == DEFAULT_SSH_KEYS_DIR
    assert global_config.systemd_env_folder == DEFAULT_SYSTEMD_ENV_DIR
    assert global_config.portforward_config_check_interval_sec == DEFAULT_PORTFORWARD_CONFIG_CHECK_INTERVAL_SEC


def test_load_global_config_applies_overrides(tmp_path):
    ssh_keys_folder = tmp_path / "custom-ssh"
    systemd_env_folder = tmp_path / "custom-systemd"
    config = {
        "global": {
            "ssh_keys_folder": str(ssh_keys_folder),
            "systemd_env_folder": str(systemd_env_folder),
            "portforward_config_check_interval_sec": 25,
        }
    }

    global_config = load_global_config(config)

    assert global_config.ssh_keys_folder == ssh_keys_folder.resolve()
    assert global_config.systemd_env_folder == systemd_env_folder.resolve()
    assert global_config.portforward_config_check_interval_sec == 25


def test_load_global_config_rejects_non_mapping_global():
    with pytest.raises(ConfigError) as exc_info:
        load_global_config({"global": []})

    assert "global" in str(exc_info.value).lower()


def test_load_global_config_rejects_non_positive_check_interval():
    with pytest.raises(ConfigError) as exc_info:
        load_global_config({"global": {"portforward_config_check_interval_sec": 0}})

    assert "portforward_config_check_interval_sec" in str(exc_info.value)
