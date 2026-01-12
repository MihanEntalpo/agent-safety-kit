# Agent-Safety-Kit versions history

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
