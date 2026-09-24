from __future__ import annotations

from pathlib import Path
import threading
import time
from datetime import datetime, timedelta, timezone

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


def test_state_manager_preserves_updates_from_another_process_snapshot(tmp_path, monkeypatch):
    state_path = tmp_path / "state.yaml"
    monkeypatch.setattr(state_module, "runtime_version", lambda: "1.6.9")
    first = state_module.StateManager(state_path)
    second = state_module.StateManager(state_path)

    first.update_last_version("1.7.0")
    second.update_agent_version(
        "codex",
        "0.155.0",
        updated_at=datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
    )

    reloaded = state_module.StateManager(state_path)
    assert reloaded.last_version == "1.7.0"
    assert reloaded.get_agent_version("codex").latest_version == "0.155.0"
    assert reloaded.get_agent_version("codex").updated_at == "2026-09-21T12:00:00Z"
    assert state_path.with_name("state.yaml.lock").exists()


def test_refresh_configured_agent_versions_checks_unique_types_once_per_day(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "agents:\n"
        "  codex-one:\n"
        "    type: codex\n"
        "  codex-two:\n"
        "    type: codex\n"
        "  aider:\n"
        "    type: aider\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "state.yaml"
    monkeypatch.setattr(state_module, "runtime_version", lambda: "1.6.9")
    manager = state_module.StateManager(state_path)
    monkeypatch.setattr(state_module, "_STATE_MANAGER", manager)
    monkeypatch.setattr(state_module.platform, "machine", lambda: "x86_64")
    calls = []

    class FakeAgent:
        @classmethod
        def check_latest_version(cls, *, architecture=None, timeout=30.0):
            calls.append(architecture)
            return "2.3.4"

    monkeypatch.setattr(state_module, "get_agent_class", lambda _agent_type: FakeAgent)
    first_check = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)

    assert state_module.refresh_configured_agent_versions(config_path, now=first_check) == {}
    assert calls == ["x86_64", "x86_64"]
    assert manager.get_agent_version("codex").latest_version == "2.3.4"

    state_module.refresh_configured_agent_versions(config_path, now=first_check + timedelta(hours=23))
    assert calls == ["x86_64", "x86_64"]

    state_module.refresh_configured_agent_versions(config_path, now=first_check + timedelta(days=1))
    assert calls == ["x86_64", "x86_64", "x86_64", "x86_64"]


def test_refresh_agent_versions_force_bypasses_daily_cache(tmp_path, monkeypatch):
    state_path = tmp_path / "state.yaml"
    monkeypatch.setattr(state_module, "runtime_version", lambda: "1.6.9")
    manager = state_module.StateManager(state_path)
    monkeypatch.setattr(state_module, "_STATE_MANAGER", manager)
    calls = []

    class FakeAgent:
        @classmethod
        def check_latest_version(cls, *, architecture=None, timeout=30.0):
            calls.append(architecture)
            return "3.4.5"

    monkeypatch.setattr(state_module, "get_agent_class", lambda _agent_type: FakeAgent)
    check_time = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    manager.update_agent_version("codex", "1.2.3", updated_at=check_time)

    errors = state_module.refresh_agent_versions(
        {"codex"},
        now=check_time + timedelta(minutes=1),
        force=True,
    )

    assert errors == {}
    assert calls == [state_module.platform.machine()]
    assert manager.get_agent_version("codex").latest_version == "3.4.5"
