# Agent-Safety-Kit versions history

## 1.4.2 - Prebuilt codex-glibc binaries

* Added `codex-glibc-prebuilt` agent type that installs a packaged glibc-compatible Codex binary instead of building in-VM
* Added build tooling and packaging hooks for distributing the prebuilt codex-glibc gzip artifact

## 1.4.1 - Run source-dir validation

* `run` now reports a clear error when the provided source directory does not exist

## 1.4.0 - Backup locking, systemd fix, integration tests 

* Added filesystem-based backup locking for backup-once and backup-repeated to prevent concurrent snapshots per backup folder
* Fixed systemd uninstall to remove the user unit link without relying on unsupported systemctl verbs
* Removed WorkingDirectory from the systemd unit to avoid bad unit settings on env expansion
* Increased integration test coverage

## 1.3.9 - Rich progress for long operations

* Updated create-vms progress output to use Rich multi-progress bars for long operations
* Added Rich progress bars to install-agents, including Ansible task progress
* Added detailed progress steps for VM creation and preparation

## 1.3.8 - Debug info on unsuccessful remote port forwarding

* Added info in case of -R port forwarding unsuccessful in case of remote port < 1024

## 1.3.7 - VM SSH key sync fixes

* Fixed `create-vm`/`create-vms` SSH key preparation to repair stale or mismatched `~/.config/agsekit/ssh/id_rsa.pub` before syncing it into the VM `authorized_keys`
* Fixed `create-vm`/`create-vms` local `known_hosts` sync to run with the current `agsekit` Python interpreter instead of a broken auto-discovered `pyenv` shim

## 1.3.6 - Run warning confirmation

* Added an explicit confirmation prompt in `agsekit run` after the empty-mounted-directory warning, so the agent does not start immediately when the VM-side mount looks empty
* Added an interactive mount prompt in `agsekit run` for configured-but-currently-unmounted folders, with automatic mounting on confirmation and a non-interactive failure mode when prompting is not possible
* Improved `agsekit doctor` after `snap restart multipass`: it now waits for the Multipass socket to come back and keeps rechecking affected mounts for a short time instead of relying on a single immediate post-restart snapshot
* Updated `stop-vm` to unmount all currently registered mounts of the target VM before shutting it down

## 1.3.5 - Doctor diagnostics

* Added the `agsekit doctor` command for diagnostics and safe auto-repair of known installation and configuration issues

## 1.3.4 - Ansible progress mode

* Added a compact default progress output for `ansible-playbook` runs (task counter + progress bar) with automatic fallback to standard Ansible output in `--debug` mode
* Unified Ansible playbook execution through a shared runner used by VM preparation and agent installation flows
* Added `--debug` support to `prepare`
* Switched Ansible playbook execution to `sys.executable -m ansible.cli.playbook`, so playbooks always run with the same Python interpreter as `agsekit`

## 1.3.3 - Opencode agent support

* Added support for `opencode` as a first-class agent type in configuration, installation, and runtime mapping

## 1.3.2 - Status output improvements

* Improved `status` resource formatting: RAM/Disk now show factual values in two representations (`GiB` and converted `G`) for easier comparison
* Improved `status` mismatch highlighting for RAM/Disk by applying tolerance to avoid false-positive differences from effective Multipass sizes

## 1.3.1 - Multi-VM agent bindings

* Added `agents.<name>.vms` support (YAML list or comma-separated string) and merged it with `agents.<name>.vm` for agent-to-VM bindings
* Changed empty `agents.<name>.vm` + `agents.<name>.vms` behavior: agents are now treated as configured for all VMs
* Updated `status` to show agents per VM using the new binding rules
* Updated `install-agents` default target selection: without explicit VM flags it now installs into all VMs bound to each agent

## 1.3.0 - Cline agent support

* Added support for `cline` as a first-class agent type in configuration, installation, and runtime mapping

## 1.2.6 - VM SSH automation and bundle idempotency fixes

* Reworked VM SSH preparation to use Ansible playbooks for `authorized_keys` and local `known_hosts` updates, removing interactive host-auth prompts during `create-vm`/`create-vms`
* Fixed Docker bundle user-group step to work without Ansible facts by using a fact-free VM user reference
* Fixed `pyenv`/`python` bundle idempotency checks to rely on the `~/.pyenv/bin/pyenv` marker instead of shell `PATH` lookup, preventing false reinstall failures on repeated runs

## 1.2.5 - Faster proxychains startup in run

* Moved proxychains helper scripts to VM preparation (`vm_packages.yml`): `prepare_vm` now installs `/usr/bin/proxychains_common.sh` and `/usr/bin/agsekit-run_with_proxychains.sh`
* Removed per-run proxychains helper upload to `/tmp` from `run`, reducing agent startup latency for proxychains-enabled launches

## 1.2.4 - Addmount VM selection

* Improved `addmount`: VM can now be chosen explicitly via `--vm`, selected interactively when multiple VMs are configured, and auto-selected when exactly one VM is configured

## 1.2.3 - VM-level allowed_agents

* Added `vms.<name>.allowed_agents` support (list or comma-separated string) with validation against configured agent names
* Updated `run` restrictions to use `mounts[].allowed_agents` first, then fall back to `vms.<vm>.allowed_agents`; when neither is set, all configured agents are allowed
* Extended `config-gen` to prompt for VM `allowed_agents` as a comma-separated string

## 1.2.2 - Addmount allowed_agents option

* Added `addmount` support for setting `allowed_agents` during mount creation in both non-interactive (`--allowed-agents a,b,c`) and interactive flows

## 1.2.1 - Arch Linux host support

* Added `prepare` support for Arch Linux hosts via `pacman` and AUR helpers (`yay`/`aura`) for Multipass installation
* Added coverage for Arch Linux `prepare` flow in integration tests (Docker-based)

## 1.2.0 - Claude agent support

* Added support for `claude` as a first-class agent type in configuration and runtime mapping

## 1.1.6 - Allowed agents improvements

* Improved `mounts[].allowed_agents`: now `run` also applies mount restrictions when the source path is inferred from the current working directory
* Improved `mounts[].allowed_agents` config format: it now accepts both YAML lists and comma-separated strings (for example, `allowed_agents: qwen, codex`)

## 1.1.5 - Mount-level agent restrictions

* Added `mounts[].allowed_agents` to restrict which configured agents can run from a mount source path (including its subdirectories)

## 1.1.4 - Agent-level proxychains override

* Added support for overriding proxychains at the agent level (`agents.<name>.proxychains`), including explicit empty-string override to disable VM-level proxychains for a specific agent

## 1.1.3 - Proxychains script copy from hidden paths

* Fixed proxychains helper/runner delivery into VMs when `agsekit` is installed under hidden host paths (for example, `~/.pyenv/...`): scripts are now uploaded via `stdin` + `multipass exec` instead of direct local-file transfer

## 1.1.2 - Debug coverage and stop-vm reliability

* Added the `--debug` argument across Multipass-related CLI commands to print executed commands, exit codes, and command output
* Updated host integration tests for VM lifecycle and related command behavior
* Made `stop-vm` more reliable: it now powers off the guest from inside the VM, waits up to 30 seconds, and falls back to `multipass stop --force` if needed

## 1.1.1 - Pip-upgrade output improvements

* Improved `agsekit pip-upgrade` result messages: now it reports old/new versions when upgraded and explicitly says when the current version is already the latest

## 1.1.0 - Status command

* Added the `agsekit status` command for consolidated VM, mounts, backups, and agents status reporting

## 1.0.5 - Ansible compatibility pin

* Pinned `ansible-core` dependency to `<2.19` for Python 3.10+ to keep Multipass collection compatibility during agent installation

## 1.0.4 - Mount/umount signature simplification

* Simplified `agsekit mount` and `agsekit umount` signatures to accept a positional source path with automatic mount source resolution

## 1.0.3 - Codex-glibc post-build cleanup

* Added mandatory codex-glibc binary verification after installation and cleanup of rust/cargo toolchains downloaded for codex-glibc build

## 1.0.2 - Version command

* Added the `agsekit version` command to show installed and project versions

## 1.0.1 - Backup cleanup defaults

* Made `backup-clean` available in interactive mode
* Switched the default backup cleanup method to `thin`

## 1.0.0 - VM software bundles

* Added software bundles that can be configured per VM for automatic installation during create-vm/create-vms
* Added backup cleanup functionality with the tail (removes oldest) and thin (logarithmic thinning) methods for old snapshots

## 0.9.13 - Create VM flow and agent lookup

* Allowed create-vm/create-vms to continue setup steps even when VM resources differ, reporting mismatches at the end
* Improved run error message when an agent is missing by listing available agents

## 0.9.12 - Self-update via pip

* Added the `pip-upgrade` command to update agsekit inside the active Python environment

## 0.9.11 - Mount config management

* Added the `removemount` command to delete mount entries from the YAML config after unmounting

## 0.9.10 - Add addmount command

* Added the `addmount` command to append mount entries to the YAML config with confirmation and optional immediate mounting

## 0.9.9 - Prepare/create-vm behavior alignment

* Aligned prepare with host-only setup and moved VM preparation into create-vm/create-vms

## 0.9.8 - Backup unicode workaround

* Added a workaround for corrupted unicode in file names when writing backup inode snapshots

## 0.9.7 - Proxychains installer fix

* Fixed agent installation failing when proxychains helper was missing inside the VM

## 0.9.6 - Interactive menu sections

* Updated the interactive command picker format to show sectioned command groups

## 0.9.5 - Interactive config example

* Added interactive-mode support for the `config-example` command

## 0.9.4 - Proxychains and agent run errors

* Improved proxychains handling for agent runs
* Improved error logging when agent startup fails

## 0.9.3 - Codex and proxychains updates

* Codex agent is now confirmed working
* Codex-glibc dynamic build now works
* Proxychains integration refined for agent runs and installs

## 0.9.2 - CLI localization

* Added ru/en localization for CLI messages

## 0.9.1 - Destroy VM command

* Added `destroy-vm` for deleting one or all Multipass VMs with confirmation or `-y`

## 0.9.0 - First functional version

* CLI for preparing Multipass hosts, creating VMs, and managing mounts
* Backup tooling for one-off and scheduled syncs with rsync progress and inode manifests
* Agent management for installing, configuring, and running supported AI agents
* Interactive configuration generator and workflow helpers (SSH, port forwarding, systemd)
