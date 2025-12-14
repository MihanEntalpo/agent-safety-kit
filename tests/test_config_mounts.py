import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from agsekit_cli.config import ConfigError, load_mounts_config


def test_load_mounts_config_applies_defaults(tmp_path):
    source = tmp_path / "project"
    config = {
        "vms": {"agent": {"cpu": 1, "ram": "1G", "disk": "5G"}},
        "mounts": [{"source": str(source)}],
    }

    mounts = load_mounts_config(config)
    assert len(mounts) == 1
    entry = mounts[0]

    assert entry.source == source.resolve()
    assert entry.target == Path("/home/ubuntu") / source.name
    assert entry.backup == source.parent / f"backups-{source.name}"
    assert entry.interval_minutes == 5
    assert entry.vm_name == "agent"


@pytest.mark.parametrize("invalid_value", [0, -1, "abc"])
def test_load_mounts_config_validates_interval(invalid_value):
    config = {
        "vms": {"agent": {"cpu": 1, "ram": "1G", "disk": "5G"}},
        "mounts": [{"source": "/data", "interval": invalid_value}],
    }

    with pytest.raises(ConfigError):
        load_mounts_config(config)


def test_mount_requires_vm_when_config_empty():
    config = {"mounts": [{"source": "/data"}]}

    with pytest.raises(ConfigError):
        load_mounts_config(config)


def test_mount_respects_explicit_vm():
    config = {
        "vms": {
            "agent": {"cpu": 1, "ram": "1G", "disk": "5G"},
            "second": {"cpu": 2, "ram": "2G", "disk": "10G"},
        },
        "mounts": [{"source": "/data", "vm": "second"}],
    }

    mounts = load_mounts_config(config)
    assert mounts[0].vm_name == "second"
