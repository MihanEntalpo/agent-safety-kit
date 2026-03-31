import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agsekit_cli.config import ConfigError, load_vms_config


def test_load_vms_config_parses_port_forwarding():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "port-forwarding": [
                    {"type": "remote", "host-addr": "127.0.0.1:80", "vm-addr": "127.0.0.1:8080"},
                    {"type": "local", "host-addr": "0.0.0.0:15432", "vm-addr": "127.0.0.1:5432"},
                    {"type": "socks5", "vm-addr": "127.0.0.1:8088"},
                ],
            }
        }
    }

    vms = load_vms_config(config)
    rules = vms["agent"].port_forwarding

    assert len(rules) == 3
    assert rules[0].type == "remote"
    assert rules[0].host_addr == "127.0.0.1:80"
    assert rules[0].vm_addr == "127.0.0.1:8080"
    assert rules[1].type == "local"
    assert rules[2].type == "socks5"
    assert rules[2].host_addr is None


def test_load_vms_config_validates_port_forwarding_host():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "port-forwarding": [
                    {"type": "local", "vm-addr": "127.0.0.1:80"},
                ],
            }
        }
    }

    with pytest.raises(ConfigError):
        load_vms_config(config)


def test_load_vms_config_accepts_proxychains():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "proxychains": "SOCKS5://Example.com:8080",
            }
        }
    }

    vms = load_vms_config(config)
    assert vms["agent"].proxychains == "socks5://example.com:8080"


def test_load_vms_config_discards_empty_proxychains():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "proxychains": "   ",
            }
        }
    }

    vms = load_vms_config(config)
    assert vms["agent"].proxychains is None


def test_load_vms_config_rejects_non_string_proxychains():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "proxychains": 123,
            }
        }
    }

    with pytest.raises(ConfigError):
        load_vms_config(config)


def test_load_vms_config_rejects_invalid_proxychains_format():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "proxychains": "localhost:8080",
            }
        }
    }

    with pytest.raises(ConfigError):
        load_vms_config(config)


def test_load_vms_config_accepts_http_proxy_upstream_string():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "http_proxy": "SOCKS5://Example.com:8080",
            }
        }
    }

    vms = load_vms_config(config)
    assert vms["agent"].http_proxy is not None
    assert vms["agent"].http_proxy.upstream == "socks5://example.com:8080"
    assert vms["agent"].http_proxy.listen is None


def test_load_vms_config_accepts_http_proxy_url_mode():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "http_proxy": {"url": "HTTP://Example.com:18881"},
            }
        }
    }

    vms = load_vms_config(config)
    assert vms["agent"].http_proxy is not None
    assert vms["agent"].http_proxy.url == "http://example.com:18881"


def test_load_vms_config_accepts_http_proxy_with_listen():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "http_proxy": {"listen": "8585", "upstream": "socks5://127.0.0.1:8181"},
            }
        }
    }

    vms = load_vms_config(config)
    assert vms["agent"].http_proxy is not None
    assert vms["agent"].http_proxy.listen == "127.0.0.1:8585"


def test_load_vms_config_rejects_http_proxy_url_and_upstream():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "http_proxy": {
                    "url": "http://127.0.0.1:18881",
                    "upstream": "socks5://127.0.0.1:8181",
                },
            }
        }
    }

    with pytest.raises(ConfigError):
        load_vms_config(config)


def test_load_vms_config_accepts_allowed_agents():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "allowed_agents": ["qwen", "codex"],
            }
        },
        "agents": {
            "qwen": {"type": "qwen"},
            "codex": {"type": "codex"},
        },
    }

    vms = load_vms_config(config)
    assert vms["agent"].allowed_agents == ["qwen", "codex"]


def test_load_vms_config_accepts_allowed_agents_as_comma_separated_string():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "allowed_agents": "qwen, codex",
            }
        },
        "agents": {
            "qwen": {"type": "qwen"},
            "codex": {"type": "codex"},
        },
    }

    vms = load_vms_config(config)
    assert vms["agent"].allowed_agents == ["qwen", "codex"]


def test_load_vms_config_rejects_non_list_or_string_allowed_agents():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "allowed_agents": 42,
            }
        },
        "agents": {"qwen": {"type": "qwen"}},
    }

    with pytest.raises(ConfigError):
        load_vms_config(config)


def test_load_vms_config_rejects_invalid_allowed_agents_item():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "allowed_agents": ["qwen", ""],
            }
        },
        "agents": {"qwen": {"type": "qwen"}},
    }

    with pytest.raises(ConfigError):
        load_vms_config(config)


def test_load_vms_config_rejects_unknown_allowed_agent():
    config = {
        "vms": {
            "agent": {
                "cpu": 2,
                "ram": "2G",
                "disk": "10G",
                "allowed_agents": ["codex"],
            }
        },
        "agents": {"qwen": {"type": "qwen"}},
    }

    with pytest.raises(ConfigError):
        load_vms_config(config)
