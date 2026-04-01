from __future__ import annotations

DOCUMENTATION = r"""
    name: agsekit_multipass
    short_description: Execute Ansible tasks inside Multipass VMs
    description:
        - Minimal connection plugin used by agsekit to run builtin Ansible modules inside a Multipass VM.
        - Commands are executed via C(multipass exec), and files are transferred via C(multipass transfer).
    author: Agent Safety Kit contributors
"""

import os
import shutil
import subprocess
import tempfile
import typing as t
from pathlib import Path

from ansible.errors import AnsibleError, AnsibleFileNotFound
from ansible.module_utils.common.text.converters import to_native, to_text
from ansible.plugins.connection import ConnectionBase
from ansible.utils.display import Display
from ansible.utils.path import unfrackpath


display = Display()


def _staging_dir() -> Path:
    staging_dir = Path.home() / "agsekit-multipass-staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    return staging_dir


def _make_staging_path(prefix: str, suffix: str = "") -> str:
    fd, staged_path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=str(_staging_dir()))
    os.close(fd)
    return staged_path


def _cleanup_staging_path(path: str) -> None:
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass


def _stage_local_source(path: str) -> str:
    staged_path = _make_staging_path("agsekit-multipass-put-", Path(path).suffix)
    shutil.copyfile(path, staged_path)
    os.chmod(staged_path, 0o644)
    return staged_path


def _stage_local_destination(path: str) -> str:
    staged_path = _make_staging_path("agsekit-multipass-fetch-", Path(path).suffix)
    _cleanup_staging_path(staged_path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return staged_path


class Connection(ConnectionBase):
    transport = "agsekit_multipass"
    has_pipelining = False

    def _connect(self) -> Connection:
        if not self._connected:
            display.vvv(
                "ESTABLISH AGSEKIT MULTIPASS CONNECTION FOR VM: {0}".format(self._remote_vm_name),
                host=self._play_context.remote_addr,
            )
            self._connected = True
        return self

    @property
    def _remote_vm_name(self) -> str:
        return str(self._play_context.remote_addr or "")

    def exec_command(
        self,
        cmd: str,
        in_data: t.Optional[bytes] = None,
        sudoable: bool = True,
    ) -> t.Tuple[int, bytes, bytes]:
        super().exec_command(cmd, in_data=in_data, sudoable=sudoable)

        shell_command = to_text(cmd)
        command = ["multipass", "exec", self._remote_vm_name, "--", "/bin/sh", "-c", shell_command]
        display.vvv("EXEC {0}".format(shell_command), host=self._play_context.remote_addr)

        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if in_data is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate(in_data)
        return process.returncode, stdout or b"", stderr or b""

    def put_file(self, in_path: str, out_path: str) -> None:
        super().put_file(in_path, out_path)

        source_path = unfrackpath(in_path)
        destination_path = out_path

        display.vvv(
            "PUT {0} TO {1}:{2}".format(source_path, self._remote_vm_name, destination_path),
            host=self._play_context.remote_addr,
        )
        if not Path(source_path).exists():
            raise AnsibleFileNotFound("file or module does not exist: {0}".format(to_native(source_path)))

        staged_source_path = _stage_local_source(source_path)
        try:
            result = subprocess.run(
                ["multipass", "transfer", staged_source_path, "{0}:{1}".format(self._remote_vm_name, destination_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise AnsibleError(
                    "failed to transfer file to {0}:{1}: {2}".format(
                        self._remote_vm_name,
                        destination_path,
                        (result.stderr or result.stdout or "").strip(),
                    )
                )
        finally:
            _cleanup_staging_path(staged_source_path)

    def fetch_file(self, in_path: str, out_path: str) -> None:
        super().fetch_file(in_path, out_path)

        source_path = in_path
        destination_path = unfrackpath(out_path)

        display.vvv(
            "FETCH {0}:{1} TO {2}".format(self._remote_vm_name, source_path, destination_path),
            host=self._play_context.remote_addr,
        )

        staged_destination_path = _stage_local_destination(destination_path)
        try:
            result = subprocess.run(
                ["multipass", "transfer", "{0}:{1}".format(self._remote_vm_name, source_path), staged_destination_path],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise AnsibleError(
                    "failed to fetch file from {0}:{1}: {2}".format(
                        self._remote_vm_name,
                        source_path,
                        (result.stderr or result.stdout or "").strip(),
                    )
                )
            shutil.move(staged_destination_path, destination_path)
        finally:
            _cleanup_staging_path(staged_destination_path)

    def close(self) -> None:
        self._connected = False
