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
