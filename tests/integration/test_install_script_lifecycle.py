from __future__ import annotations

import errno
import os
import pty
import select
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import pytest


pytestmark = pytest.mark.host_integration

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install" / "install.sh"
DOCKER_IMAGE = "debian:stable-slim"


def _clean_env(overrides: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "PROXYCHAINS_CONF_FILE"):
        env.pop(key, None)
    if overrides:
        env.update(overrides)
    return env


def _run(
    command: list[str],
    check: bool = True,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    effective_env = _clean_env(env)
    return subprocess.run(command, check=check, text=True, capture_output=True, cwd=cwd, env=effective_env)


def _require_docker() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker is required for install.sh integration test")
    info = _run(["docker", "info"], check=False)
    if info.returncode != 0:
        pytest.skip(info.stderr.strip() or info.stdout.strip() or "docker daemon is unavailable")


def _run_with_tty(
    command: list[str],
    prompt_text: str,
    input_text: str,
    timeout: int,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    started_at = time.monotonic()
    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        command,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        text=False,
        env=_clean_env(env),
        close_fds=True,
    )
    os.close(slave_fd)

    output_chunks: list[str] = []
    sent_input = False
    try:
        while True:
            if time.monotonic() - started_at > timeout:
                process.kill()
                raise AssertionError(
                    "Timed out while waiting for install.sh Docker integration test to finish.\n"
                    + "".join(output_chunks)
                )

            ready, _, _ = select.select([master_fd], [], [], 0.2)
            if ready:
                try:
                    data = os.read(master_fd, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        if process.poll() is None:
                            continue
                        break
                    raise

                if not data:
                    if process.poll() is not None:
                        break
                    continue

                text = data.decode("utf-8", errors="replace")
                output_chunks.append(text)

                if not sent_input and prompt_text in "".join(output_chunks):
                    os.write(master_fd, input_text.encode("utf-8"))
                    sent_input = True

            if process.poll() is not None and not ready:
                break
    finally:
        os.close(master_fd)

    process.wait(timeout=5)
    output = "".join(output_chunks)
    return subprocess.CompletedProcess(command, 0 if process.returncode is None else process.returncode, output, "")


def test_install_sh_installs_agsekit_after_auto_installing_python_in_debian_container(tmp_path: Path) -> None:
    _require_docker()
    _run(["docker", "pull", DOCKER_IMAGE], check=True)

    wheel_dir = tmp_path / "wheelhouse"
    wheel_dir.mkdir()
    _run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(wheel_dir)],
        check=True,
        cwd=REPO_ROOT,
    )
    wheel_path = next(wheel_dir.glob("agsekit-*.whl"))

    container_name = f"agsekit-install-sh-{uuid.uuid4().hex[:8]}"
    try:
        install_result = _run_with_tty(
            [
                "docker",
                "run",
                "--rm",
                "--name",
                container_name,
                "-i",
                "-t",
                "-v",
                f"{INSTALL_SCRIPT}:/workspace/install.sh:ro",
                "-v",
                f"{wheel_dir}:/wheelhouse:ro",
                DOCKER_IMAGE,
                "sh",
                "-lc",
                (
                    "set -eu\n"
                    "if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then\n"
                    "  echo 'unexpected preinstalled python' >&2\n"
                    "  exit 1\n"
                    "fi\n"
                    "HOME=/root AGSEKIT_PACKAGE=/wheelhouse/"
                    f"{wheel_path.name} /workspace/install.sh\n"
                    "python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'\n"
                    "test -x /root/.local/share/agsekit/venv/bin/python\n"
                    "test -x /root/.local/share/agsekit/venv/bin/agsekit\n"
                    "test -L /root/.local/bin/agsekit\n"
                    "/root/.local/share/agsekit/venv/bin/agsekit --help >/dev/null\n"
                    "grep -Fqx 'export PATH=\"$HOME/.local/bin:$PATH\"' /root/.profile\n"
                ),
            ],
            "Python 3.9+ was not found. Install it automatically now?",
            "y\n",
            timeout=2400,
        )

        output = install_result.stdout
        assert install_result.returncode == 0, output
        assert "Python 3.9+ was not found. Install it automatically now?" in output
        assert "Installing Python 3.9+ with apt..." in output
        assert "Installing agsekit..." in output
        assert "agsekit installed." in output
    finally:
        _run(["docker", "rm", "-f", container_name], check=False)
