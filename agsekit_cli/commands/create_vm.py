from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from . import debug_option, non_interactive_option

from ..ansible_utils import ensure_ansible_control_node_supported
from ..config import ConfigError, load_config, load_global_config, load_vms_config, resolve_config_path
from ..debug import debug_scope
from ..i18n import tr
from ..vm import MultipassError, create_all_vms_from_config, create_vm_from_config
from ..progress import ProgressManager
from ..vm_prepare import ensure_host_ssh_keypair, prepare_vm


def run_create_vms(
    config_path: Optional[str],
    *,
    debug: bool,
    progress: Optional[ProgressManager] = None,
) -> None:
    ensure_ansible_control_node_supported()
    resolved_path = resolve_config_path(Path(config_path) if config_path else None)
    try:
        config = load_config(resolved_path)
        global_config = load_global_config(config)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    with debug_scope(debug):
        if not progress:
            click.echo(tr("create_vm.creating_all", config_path=resolved_path))
        try:
            messages, mismatch_messages, statuses = create_all_vms_from_config(str(resolved_path))
        except ConfigError as exc:
            raise click.ClickException(str(exc))
        except MultipassError as exc:
            raise click.ClickException(str(exc))

        if debug:
            for message in messages:
                click.echo(message)

        if not progress:
            click.echo(tr("prepare.ensure_keypair"))
        private_key, public_key = ensure_host_ssh_keypair(
            ssh_dir=global_config.ssh_keys_folder,
            verbose=debug,
        )

        if progress is None:
            with ProgressManager(debug=debug) as owned_progress:
                _run_create_vms_with_progress(
                    vms,
                    statuses,
                    mismatch_messages,
                    private_key,
                    public_key,
                    debug=debug,
                    progress=owned_progress,
                    show_overall_task=True,
                )
            return

        _run_create_vms_with_progress(
            vms,
            statuses,
            mismatch_messages,
            private_key,
            public_key,
            debug=debug,
            progress=progress,
            show_overall_task=False,
        )


def _run_create_vms_with_progress(
    vms,
    statuses,
    mismatch_messages,
    private_key,
    public_key,
    *,
    debug: bool,
    progress: ProgressManager,
    show_overall_task: bool,
) -> None:
    overall_task = progress.add_task(tr("progress.create_vms_title"), total=len(vms)) if show_overall_task else None
    for vm in vms.values():
        vm_task = None
        try:
            if overall_task is not None:
                progress.update(overall_task, description=tr("progress.create_vms_vm_stage", vm_name=vm.name))
            vm_task = progress.add_task(tr("progress.vm_title", vm_name=vm.name), total=6)
            vm_status = statuses.get(vm.name)
            if vm_status == "created":
                progress.update(vm_task, description=tr("progress.vm_step_create"))
            else:
                progress.update(vm_task, description=tr("progress.vm_step_exists"))
            progress.advance(vm_task)
            prepare_vm(vm.name, private_key, public_key, vm.install, progress=progress, step_task_id=vm_task, debug=debug)
            if overall_task is not None:
                progress.advance(overall_task)
        except MultipassError as exc:
            raise click.ClickException(str(exc))
        finally:
            if vm_task is not None:
                progress.remove_task(vm_task)
    if overall_task is not None:
        progress.remove_task(overall_task)
    for mismatch in mismatch_messages:
        progress.print(mismatch)


@click.command(name="create-vm", help=tr("create_vm.command_help"))
@non_interactive_option
@click.argument("vm_name", required=False)
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
@debug_option
def create_vm_command(vm_name: Optional[str], config_path: Optional[str], debug: bool, non_interactive: bool) -> None:
    """Create a single VM by name from the YAML configuration."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    ensure_ansible_control_node_supported()
    resolved_path = resolve_config_path(Path(config_path) if config_path else None)

    try:
        config = load_config(resolved_path)
        global_config = load_global_config(config)
        vms = load_vms_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    target_vm = vm_name
    if not target_vm:
        if len(vms) == 1:
            target_vm = next(iter(vms.keys()))
            click.echo(tr("create_vm.default_vm", vm_name=target_vm))
        else:
            raise click.ClickException(tr("create_vm.name_required"))

    with debug_scope(debug):
        click.echo(tr("create_vm.creating", vm_name=target_vm, config_path=resolved_path))
        try:
            result = create_vm_from_config(str(resolved_path), target_vm)
        except ConfigError as exc:
            raise click.ClickException(str(exc))
        except MultipassError as exc:
            raise click.ClickException(str(exc))

        if isinstance(result, tuple):
            message, mismatch_message = result
        else:
            message = result
            mismatch_message = None

        click.echo(message)
        click.echo(tr("prepare.ensure_keypair"))
        private_key, public_key = ensure_host_ssh_keypair(
            ssh_dir=global_config.ssh_keys_folder,
            verbose=debug,
        )
        bundles = vms[target_vm].install
        try:
            with ProgressManager(debug=debug) as progress:
                vm_task = progress.add_task(tr("progress.vm_title", vm_name=target_vm), total=6)
                if message == tr("vm.already_matches", vm_name=target_vm) or mismatch_message is not None:
                    progress.update(vm_task, description=tr("progress.vm_step_exists"))
                else:
                    progress.update(vm_task, description=tr("progress.vm_step_create"))
                progress.advance(vm_task)
                prepare_vm(target_vm, private_key, public_key, bundles, progress=progress, step_task_id=vm_task, debug=debug)
        except MultipassError as exc:
            raise click.ClickException(str(exc))
        if mismatch_message:
            click.echo(mismatch_message)


@click.command(name="create-vms", help=tr("create_vm.command_all_help"))
@non_interactive_option
@click.option(
    "config_path",
    "--config",
    type=click.Path(dir_okay=False, exists=False, path_type=str),
    envvar="CONFIG_PATH",
    default=None,
    help=tr("config.option_path"),
)
@debug_option
def create_vms_command(config_path: Optional[str], debug: bool, non_interactive: bool) -> None:
    """Create all VMs described in the YAML configuration."""
    # not used parameter, explicitly removing it so IDEs/linters do not complain
    del non_interactive

    run_create_vms(config_path, debug=debug)
