# Windows VM-Side Control Node Plan

## Goal

Restore full provisioning support for native Windows hosts in:

- `agsekit up`
- `agsekit create-vm`
- `agsekit create-vms`
- `agsekit install-agents`
- related preparation flow used by these commands

without relying on native Windows as an Ansible control node.

The target behavior is:

- on Linux and macOS, provisioning continues to use host-side Ansible as it does now;
- on native Windows, the control node for provisioning is the target Multipass VM itself;
- the Windows host still owns host-side responsibilities such as `multipass`, SSH key generation, and local `known_hosts`;
- Ansible playbooks are executed inside the VM against `localhost` using `connection: local`.


## Problem Statement

### Current limitation

`agsekit` currently assumes that provisioning playbooks can always be launched on the host via:

```bash
python -m ansible.cli.playbook
```

That assumption is invalid on native Windows because upstream Ansible does not support Windows as a control node.

### Current consequence

The following flows fail on native Windows:

- `create-vm`
- `create-vms`
- `install-agents`
- `up` when it includes provisioning stages

The recent short-term fix replaced the low-level crash with an early, explicit error. That avoids a broken UX, but it does not restore functionality.

### Desired replacement

For native Windows only:

- use the Windows host to create/start the VM and bootstrap SSH access without Ansible;
- install and run Ansible inside the Ubuntu VM;
- execute existing playbooks inside that same VM against `localhost`.


## Non-Goals

- Do not redesign the Linux/macOS provisioning architecture.
- Do not rewrite all playbooks specifically for Windows.
- Do not introduce WSL as a supported host path.
- Do not require users to install Ansible manually inside the guest.
- Do not preserve current nested task-level Ansible progress on Windows; a simplified high-level progress model is acceptable and preferred.


## High-Level Design

### Design principle

Do not solve this with scattered `if is_windows()` branches through command code.

Instead, mirror the pattern already used by `prepare`:

- one factory chooses an OS-specific handler;
- the handler owns platform-specific provisioning behavior;
- the CLI commands remain thin orchestrators.

### New abstraction layer

Introduce a new provisioning handler module, for example:

- `agsekit_cli/provision_handlers.py`

with a base interface and platform-specific implementations.

### Proposed handler classes

- `ProvisionHandlerBase`
- `ProvisionLinux`
- `ProvisionMac`
- `ProvisionWindowsVmControlNode`

Linux and macOS handlers will keep the current host-side Ansible model.

Windows handler will:

- bootstrap VM SSH from the host without Ansible;
- prepare a VM-local control node workspace;
- run playbooks inside the VM against `localhost`.


## Proposed Public Interface

The handler interface should be defined around use-cases, not around individual shell commands.

Suggested methods:

- `prepare_host(*, debug: bool, progress: Optional[ProgressManager], config_path: Optional[str]) -> None`
- `prepare_vm(vm, private_key: Path, public_key: Path, bundles: Optional[list[str]], *, debug: bool, progress: Optional[ProgressManager], step_task_id=None) -> None`
- `install_agent(vm, playbook_path: Path, ssh_keys_folder: Path, proxychains: Optional[str], *, debug: bool, progress: Optional[ProgressManager], label: Optional[str]) -> None`
- `supports_nested_ansible_progress() -> bool`
- `ansible_debug_args(debug: bool) -> list[str]`

Optional additional interface split if needed:

- `ProvisionHandlerBase`
- `AnsibleRunnerBase`
- `VmControlNodeBase`

That split becomes useful if host-side and VM-side Ansible launching share logic but differ in transport.


## New Components

### 1. Provision handler factory

Add a factory function similar to `choose_prepare()`:

- `choose_provision_handler() -> ProvisionHandlerBase`

Platform mapping:

- Linux -> `ProvisionLinux`
- macOS -> `ProvisionMac`
- Windows -> `ProvisionWindowsVmControlNode`

This factory should be the single platform switch for provisioning behavior.

### 2. Host-side SSH bootstrap helpers

Current VM SSH preparation mixes multiple responsibilities into `_ensure_vm_ssh_access()`.

That should be split into host-side helpers that do not depend on Ansible:

- `bootstrap_vm_ssh_with_multipass(...)`
- `ensure_vm_authorized_keys_with_multipass(...)`
- `fetch_vm_host_public_keys_with_multipass(...)`
- `sync_vm_known_hosts(...)`

These should live in a reusable place such as:

- `agsekit_cli/vm_ssh_bootstrap.py`

They should work on every supported host platform.

### 3. VM-local control node manager

Add a new component, for example:

- `agsekit_cli/vm_local_control_node.py`

Responsibilities:

- create a control-node workspace inside the VM;
- copy automation assets into the VM;
- create a dedicated Python virtual environment inside the VM;
- install `ansible-core` into that venv;
- run `ansible-playbook` inside the VM with the required environment and extra vars.

### 4. Runner abstraction

Separate the concept of “run a playbook” from command code:

- `HostAnsibleRunner`
- `VmLocalAnsibleRunner`

Linux/macOS use `HostAnsibleRunner`.

Windows uses `VmLocalAnsibleRunner`.

This avoids baking transport assumptions into `create-vm`, `create-vms`, `install-agents`, and `vm_prepare`.


## Windows Provisioning Flow

### A. `prepare`

`prepare` remains primarily a host preparation command.

For native Windows:

1. Run the existing host dependency checks/install steps:
   - Multipass presence
   - MSYS2 if needed
   - `ssh-keygen`
   - `rsync`
2. Ensure the host SSH keypair exists and is repaired if needed.
3. Do not try to run any Ansible on the host.

No VM-side Ansible setup is required during standalone `prepare`, because `prepare` may run before any VM exists.

### B. `create-vm` / `create-vms`

For each VM on native Windows:

1. Create VM if needed via Multipass.
2. Start VM.
3. Fetch VM IPs.
4. Bootstrap SSH access from host without Ansible:
   - ensure `/home/ubuntu/.ssh`
   - ensure `authorized_keys`
   - fetch VM host public keys
   - update host `known_hosts`
5. Prepare VM-local control node:
   - create workspace directory
   - install Python venv if missing
   - install `ansible-core`
   - copy bundled playbooks and related assets
6. Execute base package playbook inside VM against `localhost`.
7. Execute requested bundle playbooks inside VM against `localhost`.

### C. `install-agents`

For each selected `(agent, vm)` target on native Windows:

1. Ensure VM is running.
2. Ensure host SSH access bootstrap is present.
3. Ensure VM-local control node is ready.
4. Copy or refresh the relevant agent installer playbook payload if needed.
5. Run the installer playbook inside the VM against `localhost`.
6. Pass through existing runtime extra vars such as `proxychains_url`.

### D. `up`

`up` remains a coordinator:

- `prepare`
- `create-vms`
- `install-agents`
- systemd stage where supported

The command itself should not contain platform-specific provisioning logic. It should delegate to the same handlers as direct command entry points.


## VM-Local Control Node Workspace

### Recommended location

Use a stable, non-temporary path inside the VM, for example:

- `/home/ubuntu/.local/share/agsekit/control-node`

Possible layout:

```text
/home/ubuntu/.local/share/agsekit/control-node/
  venv/
  project/
    ansible/
    run_with_http_proxy.sh
    run_with_proxychains.sh
    agent_scripts/
  logs/
```

### Why persistent, not temporary

Persistent workspace avoids:

- reinstalling `ansible-core` on every provisioning run;
- repeatedly copying unchanged automation payload;
- unnecessary network work and startup latency.

### Refresh model

The simplest safe model:

- each provisioning command refreshes the payload directory contents;
- the Python venv is reused unless missing;
- `ansible-core` is installed or upgraded only when needed.

Potential optimization later:

- track a payload version marker or content hash inside the VM.


## Reusing Existing Playbooks

### What can stay as-is

Most current playbooks should remain reusable if they are moved from “remote over SSH” to “local inside VM”.

Examples:

- `vm_packages.yml`
- bundle playbooks in `agsekit_cli/ansible/bundles/`
- agent installer playbooks in `agsekit_cli/ansible/agents/`

### What must change

Playbooks currently assuming SSH transport or host-side execution may need small adjustments.

Main changes:

- inventory becomes `localhost,`
- connection becomes `local`
- `ansible_python_interpreter` should point to the control-node venv Python where appropriate
- no `ansible_host`/`ansible_user`/`ansible_ssh_private_key_file` are needed for local guest-side execution

### `vm_ssh.yml`

This playbook is a special case.

It exists to bootstrap SSH access and sync `known_hosts`, but both are fundamentally host-side concerns:

- `authorized_keys` update can be done from the host via `multipass exec`;
- local `known_hosts` update must happen on the Windows host.

Therefore:

- do not reuse `vm_ssh.yml` for the Windows handler;
- instead, replace its role with dedicated host-side Python helpers.


## Progress Model

### Linux/macOS

Keep the current detailed model:

- Rich progress
- nested tasks
- Ansible task-level progress via callback plugins

### Windows

Use a simplified model by design.

Only show high-level stages such as:

- `Starting VM <name>`
- `Bootstrapping SSH for <name>`
- `Installing VM control node in <name>`
- `Installing base packages in <name>`
- `Installing bundle <bundle> in <name>`
- `Installing agent <agent> in <name>`

### Why simplify

Running Ansible inside the guest introduces an extra execution boundary. Preserving current callback-driven task progress would add complexity with limited user value.

The user explicitly requested:

- only high-level command progress for this path;
- no low-level Ansible step rendering.

### Debug interaction

For Windows:

- normal mode: show high-level progress only;
- debug mode: disable progress and stream raw command output.


## `--debug` Behavior

### Required result

When `--debug` is passed, Windows VM-side Ansible runs must become verbose in a predictable way.

### Recommendation

Centralize this in the handler/runner:

- `ansible_debug_args(debug: bool) -> list[str]`

Suggested behavior:

- `debug=False` -> `[]`
- `debug=True` -> `["-vvv"]`

### Output strategy

For Windows handler:

- normal mode:
  - do not use callback plugins;
  - either suppress normal Ansible chatter or capture it;
  - on failure, print a concise error summary and the relevant tail;
- debug mode:
  - stream guest-side command output directly to the terminal;
  - show exact `multipass exec` command when debug logging is enabled;
  - show the nested `python -m ansible.cli.playbook ... -vvv` invocation.

### Important implementation detail

Do not simulate debug by only printing the outer `multipass exec` command.

The inner Ansible invocation must receive actual verbose flags.


## Required Refactors

### 1. Remove provisioning hard-fail guard

Current early failure around `ensure_ansible_control_node_supported()` was a temporary safety measure.

After VM-side control node support exists:

- remove the guard from `up`
- remove the guard from `create-vm`
- remove the guard from `create-vms`
- remove the guard from `install-agents`

The guard may remain inside host-side runner code if that runner should never be used on Windows.

### 2. Decouple commands from host-side Ansible

Current commands still assume:

- host-side `run_ansible_playbook(...)`
- host-side `ansible_playbook_command()`

Commands should instead depend on handler methods or runner abstractions.

### 3. Split `vm_prepare.py`

Current file mixes:

- SSH keypair creation
- Multipass command execution
- host-side Ansible launching
- progress behavior
- VM preparation orchestration

Recommended split:

- `vm_prepare.py`
  - high-level orchestration only
- `vm_ssh_bootstrap.py`
  - SSH bootstrap and known_hosts sync helpers
- `ansible_runners.py`
  - host and VM-local runners
- `vm_local_control_node.py`
  - guest-side control node setup

### 4. Revisit extra vars shape

Current `vm_ssh_ansible_vars(...)` is SSH-specific.

Introduce two var builders:

- `vm_ssh_ansible_vars(...)`
- `vm_local_ansible_vars(...)`

The local variant should contain only what local playbooks actually need.


## Suggested File-Level Backlog

### New files

- `agsekit_cli/provision_handlers.py`
- `agsekit_cli/ansible_runners.py`
- `agsekit_cli/vm_ssh_bootstrap.py`
- `agsekit_cli/vm_local_control_node.py`

### Existing files to refactor

- `agsekit_cli/commands/prepare.py`
- `agsekit_cli/commands/create_vm.py`
- `agsekit_cli/commands/install_agents.py`
- `agsekit_cli/commands/up.py`
- `agsekit_cli/vm_prepare.py`
- `agsekit_cli/ansible_utils.py`
- `agsekit_cli/host_tools.py` if additional host tools become necessary
- `SPEC.md`
- Windows-related docs and command docs


## Detailed Execution Strategy

### Phase 1. Host-side SSH bootstrap extraction

Implement pure host-side helpers to replace Ansible dependence for SSH bootstrap:

- ensure VM `.ssh` directory via `multipass exec`
- append host public key to `authorized_keys` idempotently
- read `/etc/ssh/ssh_host_*_key.pub` via `multipass exec`
- update host `known_hosts` in Python

This phase is useful even before the rest of the Windows control-node work, because it cleanly separates host concerns from Ansible concerns.

### Phase 2. Provision handler introduction

Introduce the provisioning handler abstraction but keep Linux/macOS behavior identical:

- Linux/macOS handlers call current implementation
- Windows handler may initially be a stub if needed during refactor

The goal is to move platform switching out of commands.

### Phase 3. Runner abstraction

Introduce:

- `HostAnsibleRunner`
- `VmLocalAnsibleRunner`

Move command construction and execution concerns there.

Linux/macOS should still pass existing tests unchanged.

### Phase 4. VM-local control node bootstrapping

Implement:

- workspace creation
- asset transfer
- venv creation
- `ansible-core` installation
- command execution inside VM

At this stage, a minimal smoke flow should be enough:

- run a trivial local playbook inside the VM.

### Phase 5. Windows `create-vm` / `create-vms`

Switch Windows handler to:

- bootstrap SSH via host helpers
- prepare control node
- run `vm_packages`
- run bundle playbooks locally in VM

### Phase 6. Windows `install-agents`

Switch Windows handler to:

- ensure control node
- run agent installer playbook in VM locally

### Phase 7. Progress and debug polish

Implement simplified Windows progress and raw debug output behavior.

### Phase 8. Documentation and SPEC sync

Update:

- `SPEC.md`
- `README.md` / `README-ru.md`
- `docs/install.md` / `docs-ru/install.md`
- `docs/getting-started.md` / `docs-ru/getting-started.md`
- `docs/commands/up.md` / `docs-ru/commands/up.md`
- `docs/commands/create-vm.md` / `docs-ru/commands/create-vm.md`
- `docs/commands/install-agents.md` / `docs-ru/commands/install-agents.md`


## Ansible Invocation Model Inside VM

### Proposed command shape

The Windows handler should end up running something conceptually like:

```bash
/home/ubuntu/.local/share/agsekit/control-node/venv/bin/python \
  -m ansible.cli.playbook \
  -i localhost, \
  -c local \
  -e '{"ansible_connection":"local", ...}' \
  /home/ubuntu/.local/share/agsekit/control-node/project/ansible/vm_packages.yml
```

### In debug mode

Add:

```bash
-vvv
```

### Environment inside VM

Likely needed:

- `ANSIBLE_STDOUT_CALLBACK` only if explicitly wanted later
- `ANSIBLE_CALLBACK_PLUGINS` probably not needed for Windows simplified mode
- `ANSIBLE_CONNECTION_PLUGINS` probably not needed for local execution

For the Windows handler, prefer the simplest possible environment:

- no custom callback plugins by default
- local connection only


## Asset Delivery Strategy

### Assets that must be present inside the VM

- `agsekit_cli/ansible/*.yml`
- `agsekit_cli/ansible/agents/*.yml`
- `agsekit_cli/ansible/bundles/*.yml`
- `agsekit_cli/run_with_http_proxy.sh`
- `agsekit_cli/run_with_proxychains.sh`
- `agsekit_cli/agent_scripts/*`

### Delivery options

Option A:

- copy from local package checkout / site-packages into VM via `multipass transfer`

Option B:

- build a packaged tarball locally, transfer once, unpack in VM

Recommendation:

- start with tarball delivery

Why:

- fewer `multipass transfer` calls;
- simpler idempotency;
- easier to refresh entire payload;
- more predictable directory layout in the VM.

### Suggested implementation

1. Build temp tarball on host.
2. Transfer to VM.
3. Unpack into control-node project directory.
4. Remove temp tarball from VM.


## Python / ansible-core Installation Inside VM

### Assumptions

Ubuntu guest already has system Python 3.

Need to ensure:

- `python3 -m venv` works

If `python3-venv` is missing, install it before creating the control-node venv.

### Version policy

The control-node venv inside the VM should install the same supported Ansible range as `pyproject.toml`.

This version policy must not be duplicated manually in multiple places.

Recommendation:

- factor supported ansible requirement string into one shared constant;
- reuse it for host package metadata and VM-local setup logic where possible.


## Error Handling

### Windows normal mode

If a VM-local playbook fails:

- stop high-level progress;
- print which high-level stage failed;
- print the guest-side command;
- print captured stdout/stderr tail.

### Windows debug mode

If a VM-local playbook fails:

- output should already be visible live;
- still raise a clear `MultipassError`/`ClickException` with stage context.

### Bootstrap failures

Bootstrap errors should be separated from Ansible errors:

- failed to create `.ssh`
- failed to update `authorized_keys`
- failed to fetch host keys
- failed to install control-node dependencies
- failed to run local playbook

This distinction will matter for user troubleshooting.


## Configuration Impact

### Expected impact

The YAML config schema should not need to change.

Existing fields such as:

- VM definitions
- bundles
- agent types
- proxychains
- `http_proxy`

should continue to work unchanged.

### Internal behavior change only

This project change is an implementation-path change, not a user config change.


## Risks

### 1. Drift between host-side and VM-side playbook execution

If Linux/macOS and Windows end up using very different var sets or assumptions, behavior may diverge.

Mitigation:

- minimize special Windows-only playbook logic;
- keep playbooks generic;
- move difference into runners and var builders.

### 2. Guest bootstrap complexity

Installing `ansible-core` in the guest introduces new moving parts:

- Python venv
- package installation
- payload sync

Mitigation:

- keep control-node bootstrap isolated in one component;
- make it idempotent;
- log clearly in debug mode.

### 3. Performance overhead

Initial provisioning on Windows may become slower because of guest-side control-node setup.

Mitigation:

- reuse persistent guest venv;
- reuse payload directory;
- install only when missing or stale.

### 4. Debug UX becoming confusing

Users may see only `multipass exec` unless nested command logging is explicit.

Mitigation:

- in debug mode, always print both the outer command and the effective inner guest command.


## Testing Strategy

## Unit tests

Add tests for:

- handler selection by platform
- Windows handler avoids host-side `run_ansible_playbook(...)`
- Windows handler uses SSH bootstrap helpers
- Windows handler builds expected guest-side `ansible-playbook` command
- `--debug` adds `-vvv`
- Windows progress stays high-level
- Linux/macOS handlers preserve current host-side behavior

## Command-level tests

Update/add tests for:

- `up` on Windows no longer fails early if Windows provisioning handler exists
- `create-vm` on Windows routes through Windows handler
- `create-vms` on Windows routes through Windows handler
- `install-agents` on Windows routes through Windows handler
- `prepare` on Windows still only does host-side preparation

## Control-node bootstrap tests

Mock tests for:

- control-node workspace creation
- tarball transfer and unpack
- guest venv creation
- guest `ansible-core` installation

## Regression tests

Re-run relevant existing tests to ensure:

- Linux/macOS path is unchanged
- debug mode still disables Rich progress where expected
- docs and SPEC remain aligned

## Integration tests

Do not make Windows integration tests a blocker for the initial refactor.

First milestone should rely on unit/mock coverage.

Later, if Windows CI or host-driven tests become available, add targeted end-to-end validation.


## Documentation Changes Required

Once implemented, documentation should be updated from:

- “Windows supports install and host tooling, but not Ansible-based provisioning”

to:

- “Windows supports provisioning via VM-side control node”

Specific files likely needing updates:

- `README.md`
- `README-ru.md`
- `docs/install.md`
- `docs-ru/install.md`
- `docs/getting-started.md`
- `docs-ru/getting-started.md`
- `docs/commands/up.md`
- `docs-ru/commands/up.md`
- `docs/commands/create-vm.md`
- `docs-ru/commands/create-vm.md`
- `docs/commands/install-agents.md`
- `docs-ru/commands/install-agents.md`
- `SPEC.md`


## Suggested Commit Breakdown

A manageable implementation sequence could be:

1. Extract host-side SSH bootstrap helpers from `vm_prepare.py`
2. Introduce provisioning handler abstraction and route commands through it
3. Introduce host/VM-local Ansible runner abstraction
4. Add VM-local control node workspace bootstrap
5. Implement Windows `create-vm` / `create-vms` through VM-local control node
6. Implement Windows `install-agents` through VM-local control node
7. Simplify Windows progress and wire `--debug -> -vvv`
8. Remove temporary Windows provisioning hard-fail
9. Update tests
10. Update docs and `SPEC.md`


## Practical Acceptance Criteria

The work should be considered complete when:

- on native Windows, `agsekit prepare` still works;
- on native Windows, `agsekit create-vm` works end-to-end for a simple VM;
- on native Windows, `agsekit create-vms` works for multiple VMs;
- on native Windows, `agsekit install-agents` installs at least one supported agent type;
- on native Windows, `agsekit up` works end-to-end with the default provisioning flow;
- on native Windows, non-debug mode shows only high-level progress;
- on native Windows, `--debug` shows verbose nested guest-side Ansible output;
- Linux/macOS behavior remains unchanged;
- docs and `SPEC.md` accurately describe the final design.


## Recommended First Implementation Slice

If implementation needs to be staged with minimal risk, the best first slice is:

1. extract SSH bootstrap from Ansible;
2. add the provisioning handler abstraction;
3. implement Windows VM-local control node only for `vm_packages.yml`;
4. make `create-vm` work for a single VM on Windows;
5. expand that same path to bundles;
6. only then switch `install-agents`.

This reduces the initial blast radius while proving the central architectural idea early.
