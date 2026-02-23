import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


os.environ.setdefault("AGSEKIT_LANG", "en")

_INJECTED_ENV_VARS = (
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "DYLD_INSERT_LIBRARIES",
    "PROXYCHAINS_CONF_FILE",
    "PROXYCHAINS_QUIET_MODE",
)


@pytest.fixture(autouse=True)
def default_language(monkeypatch):
    monkeypatch.setenv("AGSEKIT_LANG", "en")


def _strip_injected_env() -> None:
    for key in _INJECTED_ENV_VARS:
        os.environ.pop(key, None)


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in _INJECTED_ENV_VARS:
        env.pop(key, None)
    return env


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        env=_clean_env(),
    )


def _host_integration_enabled() -> bool:
    return os.environ.get("AGSEKIT_RUN_HOST_IT") == "1" and sys.platform == "linux"


def _has_passwordless_sudo() -> bool:
    if os.geteuid() == 0:
        return True
    if shutil.which("sudo") is None:
        return False
    result = subprocess.run(
        ["sudo", "-n", "true"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.returncode == 0


def _needs_multipass_heal() -> bool:
    if shutil.which("multipass") is None:
        return False

    version_check = _run(["multipass", "version"])
    if version_check.returncode != 0:
        details = (version_check.stderr or "") + (version_check.stdout or "")
        markers = (
            "execv failed",
            "snap-confine is packaged without necessary permissions",
        )
        return any(marker in details for marker in markers)

    list_check = _run(["multipass", "list"])
    if list_check.returncode == 0:
        return False
    details = (list_check.stderr or "") + (list_check.stdout or "")
    return "cannot connect to the multipass socket" in details


def _heal_multipass_runtime() -> None:
    if not _host_integration_enabled():
        return
    if not _needs_multipass_heal():
        return
    if not _has_passwordless_sudo():
        return

    discard_ns = Path("/usr/lib/snapd/snap-discard-ns")
    if discard_ns.exists():
        _run(["sudo", "-n", str(discard_ns), "multipass"])
    if shutil.which("systemctl") is not None:
        _run(["sudo", "-n", "systemctl", "restart", "snapd"])
        _run(["sudo", "-n", "systemctl", "restart", "snap.multipass.multipassd.service"])

    _run(["multipass", "version"])
    _run(["multipass", "list"])


def pytest_configure(config):
    _strip_injected_env()
    if _host_integration_enabled():
        _heal_multipass_runtime()


def _host_integration_ready() -> tuple[bool, str]:
    if os.environ.get("AGSEKIT_RUN_HOST_IT") != "1":
        return False, "Set AGSEKIT_RUN_HOST_IT=1 to run host integration tests."
    if sys.platform != "linux":
        return False, "Host integration tests require Linux."
    return True, ""


def pytest_collection_modifyitems(config, items):
    enabled, reason = _host_integration_ready()
    if enabled:
        return
    skip_marker = pytest.mark.skip(reason=reason)
    for item in items:
        if "host_integration" in item.keywords:
            item.add_marker(skip_marker)


def pytest_runtest_setup(item):
    if "host_integration" not in item.keywords:
        return
    _strip_injected_env()
    _heal_multipass_runtime()
