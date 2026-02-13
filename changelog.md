# Agent-Safety-Kit versions history

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
