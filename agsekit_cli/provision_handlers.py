from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import click
from rich.progress import TaskID

from .ansible_runners import HostAnsibleRunner, VmLocalAnsibleRunner
from .ansible_utils import ansible_playbook_command, emit_hidden_output_tail
from .config import VmConfig
from .host_tools import is_windows, multipass_command
from .i18n import tr
from .progress import ProgressManager
from .vm import MultipassError, ensure_multipass_available, resolve_proxychains
from .vm_local_control_node import vm_local_ansible_vars
from .vm_prepare import (
    _ensure_vm_packages,
    _ensure_vm_ssh_access,
    _fetch_vm_ips,
    _install_vm_bundles,
    _run_multipass,
    ensure_host_ssh_keypair,
    resolve_bundles,
    vm_ssh_ansible_vars,
)
from .vm_ssh_bootstrap import bootstrap_vm_ssh_with_multipass


@dataclass
class PreparedVmSsh:
    private_key: Path
    vm_host: str


class ProvisionHandlerBase:
    def prepare_vm(
        self,
        vm_name: str,
        private_key: Path,
        public_key: Path,
        bundles: Optional[List[str]] = None,
        progress: Optional[ProgressManager] = None,
        step_task_id: Optional[TaskID] = None,
        *,
        debug: bool = False,
    ) -> None:
        raise NotImplementedError

    def install_agent(
        self,
        vm: VmConfig,
        playbook_path: Path,
        ssh_keys_folder: Path,
        proxychains: Optional[str] = None,
        *,
        prepared_ssh: Optional[PreparedVmSsh] = None,
        extra_vars_overrides: Optional[Dict[str, object]] = None,
        debug: bool = False,
        progress: Optional[ProgressManager] = None,
        label: Optional[str] = None,
    ) -> PreparedVmSsh:
        raise NotImplementedError


class ProvisionHostAnsible(ProvisionHandlerBase):
    def __init__(self) -> None:
        self.runner = HostAnsibleRunner()

    def prepare_vm(
        self,
        vm_name: str,
        private_key: Path,
        public_key: Path,
        bundles: Optional[List[str]] = None,
        progress: Optional[ProgressManager] = None,
        step_task_id: Optional[TaskID] = None,
        *,
        debug: bool = False,
    ) -> None:
        if progress and step_task_id is not None:
            progress.update(step_task_id, description=tr("progress.prepare_step_start", vm_name=vm_name))
        else:
            click.echo(tr("prepare.preparing_vm", vm_name=vm_name))
        _run_multipass(
            [multipass_command(), "start", vm_name],
            tr("prepare.starting_vm", vm_name=vm_name),
            progress=progress,
            debug=debug,
        )
        if progress and step_task_id is not None:
            progress.advance(step_task_id)
            progress.update(step_task_id, description=tr("progress.prepare_step_info", vm_name=vm_name))
        hosts = _fetch_vm_ips(vm_name, progress=progress, debug=debug)
        if not hosts:
            raise MultipassError(tr("prepare.no_vm_ips", vm_name=vm_name))
        if progress and step_task_id is not None:
            progress.advance(step_task_id)
        _ensure_vm_ssh_access(vm_name, public_key, [vm_name, *hosts], progress, step_task_id)
        vm_host = hosts[0]
        _ensure_vm_packages(vm_name, vm_host, private_key, progress, step_task_id)
        resolved_bundles = resolve_bundles(bundles or [], vm_name) if bundles else []
        _install_vm_bundles(vm_name, vm_host, private_key, resolved_bundles, progress, step_task_id)
        prepared_message = tr("prepare.prepared_vm", vm_name=vm_name)
        if progress:
            if debug:
                progress.print(prepared_message)
        else:
            click.echo(prepared_message)

    def install_agent(
        self,
        vm: VmConfig,
        playbook_path: Path,
        ssh_keys_folder: Path,
        proxychains: Optional[str] = None,
        *,
        prepared_ssh: Optional[PreparedVmSsh] = None,
        extra_vars_overrides: Optional[Dict[str, object]] = None,
        debug: bool = False,
        progress: Optional[ProgressManager] = None,
        label: Optional[str] = None,
    ) -> PreparedVmSsh:
        ensure_multipass_available()
        if prepared_ssh is None:
            private_key, public_key = ensure_host_ssh_keypair(ssh_dir=ssh_keys_folder, verbose=debug)
            hosts = _fetch_vm_ips(vm.name, progress=progress, debug=debug)
            if not hosts:
                raise MultipassError(tr("prepare.no_vm_ips", vm_name=vm.name))
            _ensure_vm_ssh_access(vm.name, public_key, [vm.name, *hosts], progress=progress)
            prepared_ssh = PreparedVmSsh(private_key=private_key, vm_host=hosts[0])
        effective_proxychains = resolve_proxychains(vm, proxychains)
        extra_vars = vm_ssh_ansible_vars(vm.name, prepared_ssh.vm_host, prepared_ssh.private_key)
        if extra_vars_overrides:
            extra_vars.update(extra_vars_overrides)
        install_command = [
            *ansible_playbook_command(),
            "-i",
            "localhost,",
            "-e",
            json.dumps(extra_vars, ensure_ascii=False),
        ]
        if effective_proxychains:
            install_command.extend(["-e", f"proxychains_url={effective_proxychains}"])
        install_command.append(str(playbook_path))
        result = self.runner.run_playbook(
            install_command,
            playbook_path=playbook_path,
            progress=progress,
            label=label,
        )
        if result.returncode != 0:
            self._log_failed_command(
                install_command,
                result,
                tr("install_agents.installer_execution_label"),
                progress=progress,
            )
            raise MultipassError(tr("install_agents.install_failed", vm_name=vm.name, code=result.returncode))
        return prepared_ssh

    @staticmethod
    def _log_failed_command(
        command: List[str],
        result: subprocess.CompletedProcess[str],
        description: str,
        *,
        progress: Optional[ProgressManager] = None,
    ) -> None:
        if progress and hasattr(progress, "halt"):
            progress.halt()
        click.echo(tr("install_agents.command_failed", description=description, code=result.returncode), err=True)
        click.echo(tr("install_agents.command_label", command=" ".join(shlex.quote(part) for part in command)), err=True)
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        if stdout:
            click.echo(tr("install_agents.stdout_label", output=stdout), err=True)
        if stderr:
            click.echo(tr("install_agents.stderr_label", output=stderr), err=True)
        emit_hidden_output_tail(result, err=True)


class ProvisionWindowsVmControlNode(ProvisionHandlerBase):
    def __init__(self) -> None:
        self.vm_runners: Dict[str, VmLocalAnsibleRunner] = {}
        self.ready_vms: set[str] = set()

    def prepare_vm(
        self,
        vm_name: str,
        private_key: Path,
        public_key: Path,
        bundles: Optional[List[str]] = None,
        progress: Optional[ProgressManager] = None,
        step_task_id: Optional[TaskID] = None,
        *,
        debug: bool = False,
    ) -> None:
        if progress and step_task_id is not None:
            progress.update(step_task_id, description=tr("progress.prepare_step_start", vm_name=vm_name))
        else:
            click.echo(tr("prepare.preparing_vm", vm_name=vm_name))
        _run_multipass(
            [multipass_command(), "start", vm_name],
            tr("prepare.starting_vm", vm_name=vm_name),
            progress=progress,
            debug=debug,
        )
        if progress and step_task_id is not None:
            progress.advance(step_task_id)
            progress.update(step_task_id, description=tr("progress.prepare_step_info", vm_name=vm_name))
        hosts = _fetch_vm_ips(vm_name, progress=progress, debug=debug)
        if not hosts:
            raise MultipassError(tr("prepare.no_vm_ips", vm_name=vm_name))
        if progress and step_task_id is not None:
            progress.advance(step_task_id)
            progress.update(step_task_id, description=tr("progress.prepare_step_ssh"))
        bootstrap_vm_ssh_with_multipass(
            vm_name,
            public_key,
            [vm_name, *hosts],
            progress=progress,
            debug=debug,
        )
        if progress and step_task_id is not None:
            progress.advance(step_task_id)
            progress.update(step_task_id, description=tr("progress.prepare_step_control_node", vm_name=vm_name))
        runner = self._runner(vm_name)
        self._ensure_runner_ready(vm_name, runner, progress=progress, debug=debug)
        if progress and step_task_id is not None:
            progress.advance(step_task_id)
            progress.update(step_task_id, description=tr("progress.prepare_step_packages"))
        packages_result = runner.run_playbook(
            Path(__file__).resolve().parent / "ansible" / "vm_packages.yml",
            extra_vars=vm_local_ansible_vars(vm_name),
            progress=progress,
            debug=debug,
        )
        if packages_result.returncode != 0:
            self._log_local_failure(vm_name, packages_result, tr("prepare.install_failed", vm_name=vm_name), progress=progress)
            raise MultipassError(tr("prepare.install_failed", vm_name=vm_name))
        if progress and step_task_id is not None:
            progress.advance(step_task_id)

        resolved_bundles = resolve_bundles(bundles or [], vm_name) if bundles else []
        if not resolved_bundles:
            if progress and step_task_id is not None:
                progress.update(step_task_id, description=tr("progress.prepare_step_bundles_none"))
                progress.advance(step_task_id)
            elif not progress:
                click.echo(tr("prepare.install_bundles_none", vm_name=vm_name))
        else:
            if progress and step_task_id is not None:
                progress.update(step_task_id, description=tr("progress.prepare_step_bundles"))
            else:
                click.echo(tr("prepare.install_bundles_start", vm_name=vm_name, bundles=", ".join(bundle.raw for bundle in resolved_bundles)))
            for bundle in resolved_bundles:
                if not progress:
                    click.echo(tr("prepare.install_bundle_running", vm_name=vm_name, bundle=bundle.raw))
                extra_vars = vm_local_ansible_vars(vm_name)
                if bundle.version:
                    extra_vars["bundle_version"] = bundle.version
                result = runner.run_playbook(bundle.playbook, extra_vars=extra_vars, progress=progress, debug=debug)
                if result.returncode != 0:
                    self._log_local_failure(
                        vm_name,
                        result,
                        tr("prepare.install_bundle_failed", vm_name=vm_name, bundle=bundle.raw),
                        progress=progress,
                    )
                    raise MultipassError(tr("prepare.install_bundle_failed", vm_name=vm_name, bundle=bundle.raw))
            if progress and step_task_id is not None:
                progress.advance(step_task_id)

        prepared_message = tr("prepare.prepared_vm", vm_name=vm_name)
        if progress:
            if debug:
                progress.print(prepared_message)
        else:
            click.echo(prepared_message)

    def install_agent(
        self,
        vm: VmConfig,
        playbook_path: Path,
        ssh_keys_folder: Path,
        proxychains: Optional[str] = None,
        *,
        prepared_ssh: Optional[PreparedVmSsh] = None,
        extra_vars_overrides: Optional[Dict[str, object]] = None,
        debug: bool = False,
        progress: Optional[ProgressManager] = None,
        label: Optional[str] = None,
    ) -> PreparedVmSsh:
        del label
        ensure_multipass_available()
        if prepared_ssh is None:
            private_key, public_key = ensure_host_ssh_keypair(ssh_dir=ssh_keys_folder, verbose=debug)
            hosts = _fetch_vm_ips(vm.name, progress=progress, debug=debug)
            if not hosts:
                raise MultipassError(tr("prepare.no_vm_ips", vm_name=vm.name))
            bootstrap_vm_ssh_with_multipass(
                vm.name,
                public_key,
                [vm.name, *hosts],
                progress=progress,
                debug=debug,
            )
            prepared_ssh = PreparedVmSsh(private_key=private_key, vm_host=hosts[0])
        runner = self._runner(vm.name)
        self._ensure_runner_ready(vm.name, runner, progress=progress, debug=debug)
        effective_proxychains = resolve_proxychains(vm, proxychains)
        extra_vars = vm_local_ansible_vars(vm.name, extra_vars_overrides)
        if effective_proxychains:
            extra_vars["proxychains_url"] = effective_proxychains
        result = runner.run_playbook(playbook_path, extra_vars=extra_vars, progress=progress, debug=debug)
        if result.returncode != 0:
            self._log_local_failure(
                vm.name,
                result,
                tr("install_agents.install_failed", vm_name=vm.name, code=result.returncode),
                progress=progress,
            )
            raise MultipassError(tr("install_agents.install_failed", vm_name=vm.name, code=result.returncode))
        return prepared_ssh

    def _runner(self, vm_name: str) -> VmLocalAnsibleRunner:
        runner = self.vm_runners.get(vm_name)
        if runner is None:
            runner = VmLocalAnsibleRunner(vm_name)
            self.vm_runners[vm_name] = runner
        return runner

    def _ensure_runner_ready(
        self,
        vm_name: str,
        runner: VmLocalAnsibleRunner,
        *,
        progress: Optional[ProgressManager],
        debug: bool,
    ) -> None:
        if vm_name in self.ready_vms:
            return
        runner.ensure_ready(progress=progress, debug=debug)
        self.ready_vms.add(vm_name)

    @staticmethod
    def _log_local_failure(
        vm_name: str,
        result: subprocess.CompletedProcess[str],
        description: str,
        *,
        progress: Optional[ProgressManager] = None,
    ) -> None:
        del vm_name
        if progress and hasattr(progress, "halt"):
            progress.halt()
        click.echo(description, err=True)
        stdout = result.stdout.strip() if isinstance(result.stdout, str) else ""
        stderr = result.stderr.strip() if isinstance(result.stderr, str) else ""
        if stdout:
            click.echo(tr("install_agents.stdout_label", output=stdout), err=True)
        if stderr:
            click.echo(tr("install_agents.stderr_label", output=stderr), err=True)


_SHARED_WINDOWS_HANDLER = ProvisionWindowsVmControlNode()
_SHARED_HOST_HANDLER = ProvisionHostAnsible()


def choose_provision_handler() -> ProvisionHandlerBase:
    if is_windows():
        return _SHARED_WINDOWS_HANDLER
    return _SHARED_HOST_HANDLER
