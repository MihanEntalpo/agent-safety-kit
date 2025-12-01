import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from agsekit_cli.config import ConfigError, load_mounts_config


def test_load_mounts_config_applies_defaults(tmp_path):
    source = tmp_path / "project"
    config = {"mounts": [{"source": str(source)}]}

    mounts = load_mounts_config(config)
    assert len(mounts) == 1
    entry = mounts[0]

    assert entry.source == source.resolve()
    assert entry.target == Path("/home/ubuntu") / source.name
    assert entry.backup == source.parent / f"backups-{source.name}"
    assert entry.interval_minutes == 5


@pytest.mark.parametrize("invalid_value", [0, -1, "abc"])
def test_load_mounts_config_validates_interval(invalid_value):
    config = {"mounts": [{"source": "/data", "interval": invalid_value}]}

    with pytest.raises(ConfigError):
        load_mounts_config(config)
