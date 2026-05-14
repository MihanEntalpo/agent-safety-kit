from __future__ import annotations

from pathlib import Path
import threading
import time

from agsekit_cli import state as state_module


def test_state_manager_sanitizes_invalid_payload_and_removes_unknown_fields(tmp_path, monkeypatch):
    state_path = tmp_path / "state.yaml"
    state_path.write_text(
        "current_version: not-a-version\nlast_Version: also-bad\nextra: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(state_module, "runtime_version", lambda: "1.6.9")

    manager = state_module.StateManager(state_path)

    assert manager.current_version == "1.6.9"
    assert manager.last_version == "1.6.9"

    content = state_path.read_text(encoding="utf-8")
    assert content.startswith(state_module.STATE_FILE_HEADER)
    assert "current_version: 1.6.9" in content
    assert "last_Version: 1.6.9" in content
    assert "extra:" not in content


def test_state_manager_persists_updated_last_version(tmp_path, monkeypatch):
    state_path = tmp_path / "state.yaml"
    monkeypatch.setattr(state_module, "runtime_version", lambda: "1.6.9")

    manager = state_module.StateManager(state_path)
    manager.update_last_version("1.7.0")

    assert manager.last_version == "1.7.0"
    assert "last_Version: 1.7.0" in state_path.read_text(encoding="utf-8")


def test_state_manager_writes_defaults_for_missing_file(tmp_path, monkeypatch):
    state_path = tmp_path / "state.yaml"
    monkeypatch.setattr(state_module, "runtime_version", lambda: "1.6.9")

    manager = state_module.StateManager(state_path)

    assert manager.current_version == "1.6.9"
    assert manager.last_version == "1.6.9"
    content = state_path.read_text(encoding="utf-8")
    assert content.startswith(state_module.STATE_FILE_HEADER)
    assert "current_version: 1.6.9" in content
    assert "last_Version: 1.6.9" in content


def test_state_manager_reads_existing_valid_file(tmp_path, monkeypatch):
    state_path = tmp_path / "state.yaml"
    state_path.write_text(
        state_module.STATE_FILE_HEADER + "current_version: 1.0.0\nlast_Version: 1.2.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(state_module, "runtime_version", lambda: "1.6.9")

    manager = state_module.StateManager(state_path)

    assert manager.current_version == "1.6.9"
    assert manager.last_version == "1.2.0"


def test_state_manager_reentrant_lock_blocks_other_threads_during_update(tmp_path, monkeypatch):
    state_path = tmp_path / "state.yaml"
    monkeypatch.setattr(state_module, "runtime_version", lambda: "1.6.9")
    manager = state_module.StateManager(state_path)
    started = threading.Event()
    finished = threading.Event()

    def _update() -> None:
        started.set()
        manager.update_last_version("1.7.0")
        finished.set()

    with manager._lock:
        worker = threading.Thread(target=_update)
        worker.start()
        started.wait(timeout=1)
        time.sleep(0.05)
        assert finished.is_set() is False

    worker.join(timeout=1)
    assert finished.is_set() is True
    assert manager.last_version == "1.7.0"


def test_state_manager_skips_rewriting_when_update_does_not_change_value(tmp_path, monkeypatch):
    state_path = tmp_path / "state.yaml"
    monkeypatch.setattr(state_module, "runtime_version", lambda: "1.6.9")
    manager = state_module.StateManager(state_path)

    before = state_path.read_text(encoding="utf-8")
    manager.update_last_version("1.6.9")
    after = state_path.read_text(encoding="utf-8")

    assert after == before
