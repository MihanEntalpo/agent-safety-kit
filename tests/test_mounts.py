import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.mounts as mounts_module
from agsekit_cli.config import MountConfig


def test_load_multipass_mounts_parses_registered_mounts(monkeypatch):
    class Result:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    payload = """
{
  "info": {
    "agent": {
      "mounts": {
        "/host/project": {
          "mount_path": "/home/ubuntu/project"
        },
        "/host/data": "/home/ubuntu/data"
      }
    },
    "empty": {
      "mounts": null
    }
  }
}
"""

    monkeypatch.setattr(mounts_module, "ensure_multipass_available", lambda: None)
    monkeypatch.setattr(
        mounts_module.subprocess,
        "run",
        lambda *args, **kwargs: Result(0, stdout=payload),
    )

    mounted = mounts_module.load_multipass_mounts()

    assert mounted["agent"] == {
        (Path("/host/project").resolve(), Path("/home/ubuntu/project").resolve()),
        (Path("/host/data").resolve(), Path("/home/ubuntu/data").resolve()),
    }
    assert mounted["empty"] == set()


def test_mount_directory_uses_default_mount_command(monkeypatch):
    mount = MountConfig(
        source=Path("/host/project"),
        target=Path("/home/ubuntu/project"),
        vm_name="agent",
        backup=Path("/host/backups"),
        interval_minutes=3,
        max_backups=10,
        backup_clean_method="thin",
    )

    call: dict[str, object] = {}

    def fake_run_multipass(command, error_message, allow_already_mounted=False):
        call["command"] = command
        call["error_message"] = error_message
        call["allow_already_mounted"] = allow_already_mounted

    monkeypatch.setattr(mounts_module, "_run_multipass", fake_run_multipass)

    mounts_module.mount_directory(mount)

    assert call["command"] == [
        "multipass",
        "mount",
        str(mount.source),
        f"{mount.vm_name}:{mount.target}",
    ]
    assert call["allow_already_mounted"] is True
