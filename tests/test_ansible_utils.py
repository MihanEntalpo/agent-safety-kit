from __future__ import annotations

import sys

import pytest

from agsekit_cli.ansible_utils import AnsibleCollectionError, ensure_multipass_collection


def _result(returncode: int = 0, stdout: str = "", stderr: str = ""):
    class Result:
        def __init__(self) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    return Result()


def test_ensure_multipass_collection_uses_current_python(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(command, check=False, capture_output=False, text=False):
        del check, capture_output, text
        calls.append(command)
        return _result(returncode=0, stdout="theko2fi.multipass 1.0.0")

    monkeypatch.setattr("agsekit_cli.ansible_utils.subprocess.run", fake_run)

    ensure_multipass_collection()

    assert len(calls) == 1
    assert calls[0][:3] == [sys.executable, "-m", "ansible.cli.galaxy"]
    assert calls[0][3:] == ["collection", "list", "theko2fi.multipass"]


def test_ensure_multipass_collection_installs_when_missing(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(command, check=False, capture_output=False, text=False):
        del check, capture_output, text
        calls.append(command)
        if command[-3:] == ["collection", "list", "theko2fi.multipass"]:
            return _result(returncode=1)
        return _result(returncode=0)

    monkeypatch.setattr("agsekit_cli.ansible_utils.subprocess.run", fake_run)
    monkeypatch.setattr("agsekit_cli.ansible_utils.click.echo", lambda *_args, **_kwargs: None)

    ensure_multipass_collection()

    assert len(calls) == 2
    assert calls[0][:3] == [sys.executable, "-m", "ansible.cli.galaxy"]
    assert calls[1][:3] == [sys.executable, "-m", "ansible.cli.galaxy"]
    assert calls[1][3:] == ["collection", "install", "theko2fi.multipass"]


def test_ensure_multipass_collection_reports_missing_ansible_galaxy(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr("agsekit_cli.ansible_utils.subprocess.run", fake_run)

    with pytest.raises(AnsibleCollectionError) as exc_info:
        ensure_multipass_collection()

    assert "ansible-galaxy" in str(exc_info.value)
