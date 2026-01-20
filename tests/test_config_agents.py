from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agsekit_cli.config import ConfigError, load_agents_config


def test_load_agents_config_defaults(tmp_path):
    config = {
        "vms": {"agent": {"cpu": 1, "ram": "1G", "disk": "5G"}},
        "agents": {
            "qwen": {
                "type": "qwen",
                "env": {"TOKEN": 123},
            }
        },
    }

    agents = load_agents_config(config)
    agent = agents["qwen"]

    assert agent.type == "qwen"
    assert agent.env == {"TOKEN": "123"}
    assert agent.vm_name == "agent"


def test_load_agents_config_validates_type():
    config = {"agents": {"demo": {"type": "unknown"}}}

    with pytest.raises(ConfigError):
        load_agents_config(config)


def test_load_agents_config_rejects_bad_env():
    config = {"agents": {"demo": {"type": "qwen", "env": "oops"}}}

    with pytest.raises(ConfigError):
        load_agents_config(config)
