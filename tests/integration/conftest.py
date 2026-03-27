from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.utils import clean_env, run_cmd, skip_if_systemd_user_unavailable


SERVICE_NAME = "agsekit-portforward"
ENV_PATH = Path.home() / ".config" / "agsekit" / "systemd.env"
UNIT_LINK_PATH = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"


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
