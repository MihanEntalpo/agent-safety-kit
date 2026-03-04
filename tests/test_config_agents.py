from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agsekit_cli.config import ALLOWED_AGENT_TYPES, ConfigError, load_agents_config


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
    assert agent.vm_name is None
    assert agent.vm_names is None
    assert agent.proxychains is None
    assert agent.proxychains_defined is False


def test_load_agents_config_accepts_single_vm():
    config = {
        "vms": {
            "agent": {"cpu": 1, "ram": "1G", "disk": "5G"},
            "agent-2": {"cpu": 1, "ram": "1G", "disk": "5G"},
        },
        "agents": {
            "qwen": {
                "type": "qwen",
                "vm": "agent-2",
            }
        },
    }

    agent = load_agents_config(config)["qwen"]

    assert agent.vm_name == "agent-2"
    assert agent.vm_names == ["agent-2"]


def test_load_agents_config_accepts_multi_vms_from_string():
    config = {
        "vms": {
            "agent": {"cpu": 1, "ram": "1G", "disk": "5G"},
            "agent-2": {"cpu": 1, "ram": "1G", "disk": "5G"},
        },
        "agents": {
            "qwen": {
                "type": "qwen",
                "vms": "agent-2, agent",
            }
        },
    }

    agent = load_agents_config(config)["qwen"]

    assert agent.vm_name == "agent-2"
    assert agent.vm_names == ["agent-2", "agent"]


def test_load_agents_config_empty_vm_and_vms_means_all_vms():
    config = {
        "vms": {
            "agent": {"cpu": 1, "ram": "1G", "disk": "5G"},
            "agent-2": {"cpu": 1, "ram": "1G", "disk": "5G"},
        },
        "agents": {
            "qwen": {
                "type": "qwen",
                "vm": " ",
                "vms": "   ",
            }
        },
    }

    agent = load_agents_config(config)["qwen"]

    assert agent.vm_name is None
    assert agent.vm_names is None


def test_load_agents_config_accepts_vm_and_vms_union():
    config = {
        "vms": {
            "agent": {"cpu": 1, "ram": "1G", "disk": "5G"},
            "agent-2": {"cpu": 1, "ram": "1G", "disk": "5G"},
        },
        "agents": {
            "qwen": {
                "type": "qwen",
                "vm": "agent",
                "vms": ["agent-2", "agent"],
            }
        },
    }

    agent = load_agents_config(config)["qwen"]

    assert agent.vm_name == "agent"
    assert agent.vm_names == ["agent", "agent-2"]


def test_load_agents_config_rejects_unknown_vms():
    config = {
        "vms": {"agent": {"cpu": 1, "ram": "1G", "disk": "5G"}},
        "agents": {
            "qwen": {
                "type": "qwen",
                "vms": "agent,missing",
            }
        },
    }

    with pytest.raises(ConfigError):
        load_agents_config(config)


def test_load_agents_config_rejects_invalid_vms_value():
    config = {
        "vms": {"agent": {"cpu": 1, "ram": "1G", "disk": "5G"}},
        "agents": {
            "qwen": {
                "type": "qwen",
                "vms": 123,
            }
        },
    }

    with pytest.raises(ConfigError):
        load_agents_config(config)


def test_load_agents_config_accepts_proxychains_override():
    config = {
        "vms": {"agent": {"cpu": 1, "ram": "1G", "disk": "5G"}},
        "agents": {
            "qwen": {
                "type": "qwen",
                "proxychains": "SOCKS5://Example.com:8080",
            }
        },
    }

    agents = load_agents_config(config)
    agent = agents["qwen"]

    assert agent.proxychains == "socks5://example.com:8080"
    assert agent.proxychains_defined is True


def test_load_agents_config_keeps_empty_proxychains_as_override():
    config = {
        "vms": {"agent": {"cpu": 1, "ram": "1G", "disk": "5G"}},
        "agents": {
            "qwen": {
                "type": "qwen",
                "proxychains": "   ",
            }
        },
    }

    agents = load_agents_config(config)
    agent = agents["qwen"]

    assert agent.proxychains is None
    assert agent.proxychains_defined is True


def test_load_agents_config_validates_type():
    config = {"agents": {"demo": {"type": "unknown"}}}

    with pytest.raises(ConfigError):
        load_agents_config(config)


def test_load_agents_config_rejects_bad_env():
    config = {"agents": {"demo": {"type": "qwen", "env": "oops"}}}

    with pytest.raises(ConfigError):
        load_agents_config(config)


def test_load_agents_config_rejects_invalid_proxychains_type():
    config = {"agents": {"demo": {"type": "qwen", "proxychains": 123}}}

    with pytest.raises(ConfigError):
        load_agents_config(config)


def test_load_agents_config_requires_type_for_known_agent_name():
    config = {
        "vms": {"agent": {"cpu": 1, "ram": "1G", "disk": "5G"}},
        "agents": {
            "qwen": {
                "env": {"TOKEN": "abc"},
            }
        },
    }

    with pytest.raises(ConfigError):
        load_agents_config(config)


def test_load_agents_config_requires_type_for_unknown_agent_name():
    config = {"agents": {"demo": {"env": {}}}}

    with pytest.raises(ConfigError):
        load_agents_config(config)


@pytest.mark.parametrize("agent_type", sorted(set(ALLOWED_AGENT_TYPES.values())))
def test_load_agents_config_supports_allowed_agent_types(agent_type: str):
    config = {
        "vms": {"agent": {"cpu": 1, "ram": "1G", "disk": "5G"}},
        "agents": {
            "main": {"type": agent_type},
        },
    }

    agents = load_agents_config(config)

    assert agents["main"].type == agent_type
