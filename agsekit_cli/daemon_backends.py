from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
import plistlib
import re
import subprocess
from pathlib import Path
from typing import List, Optional

import click

from . import cli_entry, systemd_backend
from .config import resolve_config_path
from .i18n import tr

LAUNCHD_LABEL = "org.agsekit.portforward"
STATUS_LOG_LINES = 10


def platform_label(system_name: Optional[str] = None) -> str:
    system = system_name
    if system is None:
        import platform as _platform
        system = _platform.system()
    if system == "Darwin":
        return "macOS"
    if system == "Windows":
        return "Windows"
    return system or "this platform"


class DaemonBackend(ABC):
    @property
    @abstractmethod
    def supported(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def backend_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def install(self, config_path: Optional[Path], *, project_dir: Optional[Path] = None, announce: bool = True) -> None:
        raise NotImplementedError

    @abstractmethod
    def uninstall(self, *, project_dir: Optional[Path] = None, announce: bool = True) -> None:
        raise NotImplementedError

    @abstractmethod
    def start(self, *, announce: bool = True) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self, *, announce: bool = True) -> None:
        raise NotImplementedError

    @abstractmethod
    def restart(self, *, announce: bool = True) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop_if_installed(self, *, announce: bool = True) -> bool:
        raise NotImplementedError

    @abstractmethod
    def status_lines(self) -> List[str]:
        raise NotImplementedError


class UnsupportedDaemonBackend(DaemonBackend):
    def __init__(self, system_name: str) -> None:
        self.system_name = system_name

    @property
    def supported(self) -> bool:
        return False

    @property
    def backend_name(self) -> str:
        return "unsupported"

    def install(self, config_path: Optional[Path], *, project_dir: Optional[Path] = None, announce: bool = True) -> None:
        del config_path, project_dir, announce

    def uninstall(self, *, project_dir: Optional[Path] = None, announce: bool = True) -> None:
        del project_dir, announce

    def start(self, *, announce: bool = True) -> None:
        del announce

    def stop(self, *, announce: bool = True) -> None:
        del announce

    def restart(self, *, announce: bool = True) -> None:
        del announce

    def stop_if_installed(self, *, announce: bool = True) -> bool:
        del announce
        return False

    def status_lines(self) -> List[str]:
        return [tr("daemon.unsupported_platform", platform=platform_label(self.system_name))]


class SystemdDaemonBackend(DaemonBackend):
    @property
    def supported(self) -> bool:
        return True

    @property
    def backend_name(self) -> str:
        return "systemd"

    def install(self, config_path: Optional[Path], *, project_dir: Optional[Path] = None, announce: bool = True) -> None:
        systemd_backend.install_portforward_service(config_path, project_dir=project_dir, announce=announce)

    def uninstall(self, *, project_dir: Optional[Path] = None, announce: bool = True) -> None:
        systemd_backend.uninstall_portforward_service(project_dir=project_dir, announce=announce)

    def start(self, *, announce: bool = True) -> None:
        systemd_backend.manage_portforward_service("start", announce=announce)

    def stop(self, *, announce: bool = True) -> None:
        systemd_backend.manage_portforward_service("stop", announce=announce)

    def restart(self, *, announce: bool = True) -> None:
        systemd_backend.manage_portforward_service("restart", announce=announce)

    def stop_if_installed(self, *, announce: bool = True) -> bool:
        return systemd_backend.stop_portforward_service(announce=announce)

    def status_lines(self) -> List[str]:
        return systemd_backend.render_status_lines(systemd_backend.get_portforward_service_status())


@dataclass
class LaunchdServiceStatus:
    label: str
    plist_path: str
    installed: bool
    loaded: str
    enabled: str
    pid: str
    state: str
    last_exit_status: str
    stdout_log: str
    stderr_log: str
    stdout_tail: List[str]
    stderr_tail: List[str]


class LaunchdDaemonBackend(DaemonBackend):
    @property
    def supported(self) -> bool:
        return True

    @property
    def backend_name(self) -> str:
        return "launchd"

    @property
    def launch_agents_dir(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents"

    @property
    def plist_path(self) -> Path:
        return self.launch_agents_dir / f"{LAUNCHD_LABEL}.plist"

    @property
    def logs_dir(self) -> Path:
        return Path.home() / "Library" / "Logs" / "agsekit"

    @property
    def stdout_log_path(self) -> Path:
        return self.logs_dir / "daemon.stdout.log"

    @property
    def stderr_log_path(self) -> Path:
        return self.logs_dir / "daemon.stderr.log"

    @property
    def domain_target(self) -> str:
        return f"gui/{os.getuid()}"

    @property
    def job_target(self) -> str:
        return f"{self.domain_target}/{LAUNCHD_LABEL}"

    def _run_launchctl(self, command: List[str], *, announce: bool = True, check: bool = True) -> subprocess.CompletedProcess[str]:
        if announce:
            click.echo(tr("launchd.running_command", command=" ".join(command)))
        result = subprocess.run(command, capture_output=True, text=True)
        if check and result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or tr("launchd.command_failed")
            raise click.ClickException(message)
        return result

    def _query_launchctl(self, command: List[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, capture_output=True, text=True)

    def _is_loaded(self) -> bool:
        return self._query_launchctl(["launchctl", "print", self.job_target]).returncode == 0

    def _ensure_installed(self) -> None:
        if self.plist_path.exists():
            return
        raise click.ClickException(tr("daemon.not_installed"))

    def _resolve_agsekit_bin(self) -> Path:
        return cli_entry.resolve_agsekit_bin("daemon.cli_not_found")

    def _plist_data(self, config_path: Path, project_dir: Path) -> dict:
        agsekit_bin = self._resolve_agsekit_bin()
        return {
            "Label": LAUNCHD_LABEL,
            "ProgramArguments": [str(agsekit_bin), "portforward", "--config", str(config_path)],
            "RunAtLoad": True,
            "KeepAlive": True,
            "WorkingDirectory": str(project_dir),
            "StandardOutPath": str(self.stdout_log_path),
            "StandardErrorPath": str(self.stderr_log_path),
            "EnvironmentVariables": {
                "AGSEKIT_BIN": str(agsekit_bin),
                "AGSEKIT_CONFIG": str(config_path),
                "AGSEKIT_PROJECT_DIR": str(project_dir),
            },
        }

    def _write_plist(self, config_path: Path, project_dir: Path) -> None:
        self.launch_agents_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.plist_path.write_bytes(plistlib.dumps(self._plist_data(config_path, project_dir)))

    def _tail_lines(self, path: Path) -> List[str]:
        if not path.exists():
            return [tr("launchd.status_logs_empty")]
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [line.rstrip() for line in lines if line.strip()]
        if not lines:
            return [tr("launchd.status_logs_empty")]
        return lines[-STATUS_LOG_LINES:]

    def _parse_loaded_state(self, output: str, *, pattern: str, default_key: str) -> str:
        match = re.search(pattern, output, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return tr(default_key)

    def _enabled_state(self) -> str:
        result = self._query_launchctl(["launchctl", "print-disabled", self.domain_target])
        if result.returncode != 0:
            return tr("launchd.status_unknown")
        match = re.search(r'"%s"\s*=>\s*(true|false)' % re.escape(LAUNCHD_LABEL), result.stdout)
        if not match:
            return tr("launchd.status_unknown")
        return tr("status.no") if match.group(1) == "true" else tr("status.yes")

    def _status(self) -> LaunchdServiceStatus:
        installed = self.plist_path.exists()
        loaded_result = self._query_launchctl(["launchctl", "print", self.job_target]) if installed else subprocess.CompletedProcess([], 1, stdout="", stderr="")
        output = loaded_result.stdout or loaded_result.stderr
        loaded = tr("status.yes") if installed and loaded_result.returncode == 0 else tr("status.no")
        return LaunchdServiceStatus(
            label=LAUNCHD_LABEL,
            plist_path=str(self.plist_path),
            installed=installed,
            loaded=loaded,
            enabled=self._enabled_state() if installed else tr("launchd.status_unknown"),
            pid=self._parse_loaded_state(output, pattern=r"\bpid = ([^\n]+)", default_key="launchd.status_unknown") if installed and loaded_result.returncode == 0 else tr("launchd.status_unknown"),
            state=self._parse_loaded_state(output, pattern=r"\bstate = ([^\n]+)", default_key="launchd.status_unknown") if installed and loaded_result.returncode == 0 else tr("launchd.status_unknown"),
            last_exit_status=self._parse_loaded_state(output, pattern=r"last exit code = ([^\n]+)", default_key="launchd.status_unknown") if installed and loaded_result.returncode == 0 else tr("launchd.status_unknown"),
            stdout_log=str(self.stdout_log_path),
            stderr_log=str(self.stderr_log_path),
            stdout_tail=self._tail_lines(self.stdout_log_path),
            stderr_tail=self._tail_lines(self.stderr_log_path),
        )

    def install(self, config_path: Optional[Path], *, project_dir: Optional[Path] = None, announce: bool = True) -> None:
        resolved_config = resolve_config_path(config_path).resolve()
        resolved_project_dir = (project_dir or Path.cwd()).resolve()
        self._write_plist(resolved_config, resolved_project_dir)
        self._run_launchctl(["launchctl", "bootout", self.domain_target, str(self.plist_path)], announce=announce, check=False)
        self._run_launchctl(["launchctl", "bootstrap", self.domain_target, str(self.plist_path)], announce=announce)
        self._run_launchctl(["launchctl", "enable", self.job_target], announce=announce)
        self._run_launchctl(["launchctl", "kickstart", "-k", self.job_target], announce=announce)

    def uninstall(self, *, project_dir: Optional[Path] = None, announce: bool = True) -> None:
        del project_dir
        if self.plist_path.exists():
            self._run_launchctl(["launchctl", "bootout", self.domain_target, str(self.plist_path)], announce=announce, check=False)
            self.plist_path.unlink()

    def start(self, *, announce: bool = True) -> None:
        self._ensure_installed()
        if self._is_loaded():
            self._run_launchctl(["launchctl", "kickstart", self.job_target], announce=announce)
            return
        self._run_launchctl(["launchctl", "bootstrap", self.domain_target, str(self.plist_path)], announce=announce)
        self._run_launchctl(["launchctl", "enable", self.job_target], announce=announce)
        self._run_launchctl(["launchctl", "kickstart", "-k", self.job_target], announce=announce)

    def stop(self, *, announce: bool = True) -> None:
        self._ensure_installed()
        if not self._is_loaded():
            return
        self._run_launchctl(["launchctl", "bootout", self.domain_target, str(self.plist_path)], announce=announce)

    def restart(self, *, announce: bool = True) -> None:
        self._ensure_installed()
        if self._is_loaded():
            self._run_launchctl(["launchctl", "kickstart", "-k", self.job_target], announce=announce)
            return
        self._run_launchctl(["launchctl", "bootstrap", self.domain_target, str(self.plist_path)], announce=announce)
        self._run_launchctl(["launchctl", "enable", self.job_target], announce=announce)
        self._run_launchctl(["launchctl", "kickstart", "-k", self.job_target], announce=announce)

    def stop_if_installed(self, *, announce: bool = True) -> bool:
        if not self.plist_path.exists():
            return False
        if self._is_loaded():
            self._run_launchctl(["launchctl", "bootout", self.domain_target, str(self.plist_path)], announce=announce, check=False)
        return True

    def status_lines(self) -> List[str]:
        status = self._status()
        lines = [
            tr("launchd.status_label", label=status.label),
            tr("launchd.status_plist", path=status.plist_path),
            tr("launchd.status_installed", state=tr("status.yes") if status.installed else tr("status.no")),
            tr("launchd.status_loaded", state=status.loaded),
            tr("launchd.status_enabled", state=status.enabled),
            tr("launchd.status_state", state=status.state),
            tr("launchd.status_pid", pid=status.pid),
            tr("launchd.status_last_exit", status=status.last_exit_status),
            tr("launchd.status_stdout", path=status.stdout_log),
            tr("launchd.status_stderr", path=status.stderr_log),
            tr("launchd.status_stdout_logs_header"),
        ]
        lines.extend(tr("launchd.status_log_line", line=line) for line in status.stdout_tail)
        lines.append(tr("launchd.status_stderr_logs_header"))
        lines.extend(tr("launchd.status_log_line", line=line) for line in status.stderr_tail)
        return lines


def get_daemon_backend(system_name: Optional[str] = None) -> DaemonBackend:
    if system_name is None:
        import platform as _platform
        system_name = _platform.system()
    if system_name == "Linux":
        return SystemdDaemonBackend()
    if system_name == "Darwin":
        return LaunchdDaemonBackend()
    return UnsupportedDaemonBackend(system_name or "")


def is_daemon_supported_platform(system_name: Optional[str] = None) -> bool:
    return get_daemon_backend(system_name).supported


def install_portforward_daemon(config_path: Optional[Path], *, project_dir: Optional[Path] = None, announce: bool = True) -> None:
    get_daemon_backend().install(config_path, project_dir=project_dir, announce=announce)


def stop_portforward_daemon(*, announce: bool = True) -> bool:
    return get_daemon_backend().stop_if_installed(announce=announce)
