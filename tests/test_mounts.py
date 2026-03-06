import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agsekit_cli.mounts as mounts_module


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
