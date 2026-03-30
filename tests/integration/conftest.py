from __future__ import annotations

import os
from pathlib import Path
import time

import pytest

from agsekit_cli.vm import MULTIPASS_LAUNCH_TIMEOUT_ENV_VAR
from tests.integration.progress import integration_progress_enabled, progress_line, set_terminal_reporter
from tests.integration.utils import (
    clean_env,
    run_cmd,
    skip_if_systemd_user_unavailable,
)


SERVICE_NAME = "agsekit-portforward"
ENV_PATH = Path.home() / ".config" / "agsekit" / "systemd.env"
UNIT_LINK_PATH = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"


# Host integration tests are allowed to wait longer for `multipass launch`
# than the normal CLI runtime, but the timeout remains overrideable.
os.environ.setdefault(MULTIPASS_LAUNCH_TIMEOUT_ENV_VAR, "600")
_TEST_START_TIMES = {}
_TEST_OUTCOMES = {}


def pytest_configure(config):
    if integration_progress_enabled():
        config.option.capture = "no"
        set_terminal_reporter(config.pluginmanager.get_plugin("terminalreporter"))


def pytest_runtest_logstart(nodeid, location):
    del location
    if not integration_progress_enabled():
        return
    _TEST_START_TIMES[nodeid] = time.monotonic()
    _TEST_OUTCOMES[nodeid] = "running"
    progress_line(f"[IT] TEST START  {nodeid}")


def pytest_runtest_logreport(report):
    if not integration_progress_enabled():
        return
    if report.when == "setup" and report.failed:
        _TEST_OUTCOMES[report.nodeid] = report.outcome
    elif report.when == "call":
        _TEST_OUTCOMES[report.nodeid] = report.outcome
    elif report.when == "teardown" and report.failed and _TEST_OUTCOMES.get(report.nodeid) == "running":
        _TEST_OUTCOMES[report.nodeid] = report.outcome


def pytest_runtest_logfinish(nodeid, location):
    del location
    if not integration_progress_enabled():
        return
    started_at = _TEST_START_TIMES.pop(nodeid, None)
    outcome = _TEST_OUTCOMES.pop(nodeid, "unknown")
    if started_at is None:
        progress_line(f"[IT] TEST FINISH {nodeid} [{outcome}]")
        return
    duration = time.monotonic() - started_at
    progress_line(f"[IT] TEST FINISH {nodeid} [{outcome}] ({duration:.1f}s)")


def _service_state(command: str) -> bool:
    result = run_cmd(
        ["systemctl", "--user", command, SERVICE_NAME],
        check=False,
        env=clean_env(),
    )
    return result.returncode == 0


@pytest.fixture
def preserve_portforward_user_service():
    skip_if_systemd_user_unavailable()

    saved_env = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else None
    saved_target = UNIT_LINK_PATH.resolve() if UNIT_LINK_PATH.exists() else None
    was_active = _service_state("is-active")
    was_enabled = _service_state("is-enabled")

    yield {
        "env_path": ENV_PATH,
        "unit_link": UNIT_LINK_PATH,
    }

    run_cmd(["systemctl", "--user", "stop", SERVICE_NAME], check=False, env=clean_env())
    run_cmd(["systemctl", "--user", "disable", SERVICE_NAME], check=False, env=clean_env())

    if UNIT_LINK_PATH.exists() or UNIT_LINK_PATH.is_symlink():
        UNIT_LINK_PATH.unlink()

    if saved_env is None:
        if ENV_PATH.exists():
            ENV_PATH.unlink()
    else:
        ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        ENV_PATH.write_text(saved_env, encoding="utf-8")

    if saved_target is not None:
        UNIT_LINK_PATH.parent.mkdir(parents=True, exist_ok=True)
        UNIT_LINK_PATH.symlink_to(saved_target)

    run_cmd(["systemctl", "--user", "daemon-reload"], check=False, env=clean_env())

    if saved_target is not None and was_enabled:
        run_cmd(["systemctl", "--user", "enable", SERVICE_NAME], check=False, env=clean_env())

    if saved_target is not None and was_active:
        run_cmd(["systemctl", "--user", "restart", SERVICE_NAME], check=False, env=clean_env())
