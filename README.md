[README.md на русском](README-ru.md)

# Agent Safety Kit

A toolkit for running AI agents in an isolated environment inside a Multipass virtual machine.

## Why this matters

<img width="437" height="379" alt="image" src="https://github.com/user-attachments/assets/c3486072-e96a-4197-8b1f-d6ac228c2cc6" />

Some stories (you can find plenty more):

* [Qwen Coder agent destroys working builds](https://github.com/QwenLM/qwen-code/issues/354)
* [Codex keeps deleting unrelated and uncommitted files! even ignoring rejected requests](https://github.com/openai/codex/issues/4969)
* [comment: qwen-code CLI destroyed my entire project, deleted important files](https://www.reddit.com/r/DeepSeek/comments/1mmfjsl/right_now_qwen_is_the_best_model_they_have_the/)
* [Claude Code deleted my entire workspace, here's the proof](https://www.reddit.com/r/ClaudeAI/comments/1m299f5/claude_code_deleted_my_entire_workspace_heres_the/)
* [I Asked Claude Code to Fix All Bugs, and It Deleted the Whole Repo](https://levelup.gitconnected.com/i-asked-claude-code-to-fix-all-bugs-and-it-deleted-the-whole-repo-e7f24f5390c5)
* [Codex has twice deleted and corrupted my files (r/ClaudeAI comment)](https://www.reddit.com/r/ClaudeAI/comments/1nhvyu0/openai_drops_gpt5_codex_cli_right_after/)

Everyone says "you should have backups" and "everything must live in git", but console AI agents still lack built-in snapshots to roll back after every change they make. Until sandboxes catch up, this toolkit helps you manage that yourself.

## Key ideas

- The agent only works inside a virtual machine.
- The VM is launched via Multipass (a simple Canonical tool to start Ubuntu VMs with a single command).
- Project folders from the host are mounted into the VM; an automatic backup job runs in parallel to a sibling directory at a configurable interval (defaults to every five minutes and only when changes are detected), using `rsync` with hardlinks to save space.
- VM, mount, and cloud-init settings are stored in a YAML config.
- You can run the agent without entering the guest via `multipass ssh`—it still executes inside the VM.

## Quick start

1. Clone the repository and enter it:
   ```bash
   git clone https://github.com/MihanEntalpo/agent-safety-kit/
   cd agent-safety-kit
   ```

2. Set up the Python environment and install the package into the virtualenv (requires Python 3.9 or newer):
   ```bash
   python3 -m venv ./venv
   source ./venv/bin/activate
   pip install .
   ```
   This makes the `agsekit` command available inside the virtual environment.

3. Create a YAML configuration (the CLI checks `--config`, then `CONFIG_PATH`, then `~/.config/agsekit/config.yaml`):
   ```bash
   mkdir -p ~/.config/agsekit
   cp config-example.yaml ~/.config/agsekit/config.yaml
   # edit vms/mounts/cloud-init to your needs
   ```
   You can also run `agsekit config-gen` to answer a few questions and save the config (defaults to `~/.config/agsekit/config.yaml`; use `--overwrite` to replace an existing file).

4. Install required system dependencies (in particular, Multipass; requires sudo and currently works only on Debian-based systems):
   ```bash
   agsekit prepare
   ```

5. Create the virtual machines defined in YAML:
   ```bash
   agsekit create-vms
   ```

   To launch just one VM, use `agsekit create-vm <name>`. If the config contains only one VM, you can omit `<name>` and it will be used automatically. If a VM already exists, the command compares the desired resources with the current ones and reports any differences. Changing resources of an existing VM is not supported yet.

6. Mount your folders (assuming mounts are already configured in the YAML file):
   ```bash
   agsekit mount --all
   ```

7. Install all configured agents into their default VMs:
   ```bash
   agsekit install-agents --all-agents
   ```

8. Launch an agent inside its VM (example runs `qwen` in the folder where `/host/path/project` is mounted, with backups enabled by default):
   ```bash
   agsekit run qwen /host/path/project --vm agent-ubuntu
   ```
   On the very first run with backups enabled, the CLI creates an initial snapshot with progress output before launching the agent, so wait for it to complete.

## agsekit commands

### Setup and VM lifecycle

* `agsekit prepare` — installs required system dependencies (including Multipass; requires sudo and currently works only on Debian-based systems).
* `agsekit config-gen [--config <path>] [--overwrite]` — interactive wizard that asks about VMs, mounts, and agents, then writes a YAML config to the chosen path (defaults to `~/.config/agsekit/config.yaml`). Without `--overwrite`, the command warns if the file already exists.
* `agsekit create-vms` — creates every VM defined in the YAML configuration.
* `agsekit create-vm <name>` — launches just one VM. If the config contains only one VM, you can omit `<name>` and it will be used automatically. If a VM already exists, the command compares the desired resources with the current ones and reports any differences. Changing resources of an existing VM is not supported yet.
* `agsekit shell [<vm_name>] [--config <path>]` — opens an interactive `multipass ssh` session inside the chosen VM, applying any configured port forwarding. If only
  one VM is defined in the config, the CLI connects there even without `vm_name`. When several VMs exist and the command runs in
  a TTY, the CLI prompts you to pick one; in non-interactive mode, an explicit `vm_name` is required.
* `agsekit stop <vm_name> [--config <path>]` — stops the specified VM from the configuration. If only one VM is configured, the name can be omitted.
* `agsekit stop --all-vms [--config <path>]` — stops every VM declared in the config file.

### Mount management

* `agsekit mount --source-dir <path> [--config <path>]` — mounts the directory described by `source` in the configuration file (default search: `--config`, `CONFIG_PATH`, `~/.config/agsekit/config.yaml`) into its VM using `multipass mount`. Use `--all` to mount every entry from the config. When there is only one mount in the config, the command can be run without `--source-dir` or `--all`.
* `agsekit umount --source-dir <path> [--config <path>]` — unmounts the directory described by `source` in the config (or `CONFIG_PATH`/`--config`); `--all` unmounts every configured path. If only one mount is configured, the command will unmount it even without explicit flags.

### Backups

#### One-off backup

`agsekit backup-once --source-dir <path> --dest-dir <path> [--exclude <pattern> ...] [--progress]` — runs a single backup of the source directory into the specified destination using `rsync`.
The command creates a timestamped directory with a `-partial` suffix, supports incremental copies via `--link-dest` to the previous backup, and honors exclusions from `.backupignore` and `--exclude` arguments. When finished, the temporary folder is renamed to a final timestamp without the suffix. If nothing changed relative to the last backup, no new snapshot is created and the tool reports the absence of updates.
Pass `--progress` to forward rsync progress flags and show a console progress bar while files are copied.

`.backupignore` examples:
```
# exclude virtual environments and dependencies
venv/
node_modules/

# ignore temporary and log files by pattern
*.log
*.tmp

# include a specific file inside an excluded folder
!logs/important.log

# skip documentation build artifacts
docs/build/
```

Backups use `rsync` with incremental links (`--link-dest`) to the previous copy: if only a small set of files changed, the new snapshot stores just the updated data, while unchanged files are hardlinked to the prior snapshot. This keeps a chain of dated directories while consuming minimal space when changes are rare.

#### Repeated backups

* `agsekit backup-repeated --source-dir <path> --dest-dir <path> [--exclude <pattern> ...] [--interval <minutes>] [--skip-first]` — runs an immediate backup and then repeats it every `interval` minutes (defaults to five minutes). With `--skip-first`, the loop waits for the first interval before performing the initial run. After each backup it prints `Done, waiting N minutes` with the actual interval value.
* `agsekit backup-repeated-mount --mount <path> [--config <path>]` — looks up the mount by its `source` path in the configuration file (default search: `--config`, `CONFIG_PATH`, `~/.config/agsekit/config.yaml`) and launches repeated backups using the paths and interval from the config. When only one mount is present, `--mount` can be omitted; with multiple mounts, an explicit choice is required.
* `agsekit backup-repeated-all [--config <path>]` — reads all mounts from the config (default search: `--config`, `CONFIG_PATH`, `~/.config/agsekit/config.yaml`) and starts concurrent repeated backups for each entry within a single process. Use Ctrl+C to stop the loops.

### Agent installation

* `agsekit install-agents <agent_name> [<vm>|--all-vms] [--config <path>]` — runs the prepared installation script for the chosen agent type inside the specified VM (or the agent's default VM if none is provided). If the config defines only one agent, you can skip `<agent_name>` and it will be picked automatically.
* `agsekit install-agents --all-agents [--all-vms] [--config <path>]` — installs every configured agent either into their default VM or into every VM when `--all-vms` is set.

The installation scripts live in `agsekit_cli/agent_scripts/`: `codex` installs the npm CLI, `codex-glibc` builds the Rust sources with the glibc target and installs the binary as `codex-glibc`, and `qwen`/`claude-code` follow their upstream steps (the `qwen` script installs the qwen-code CLI). Other agent types are not supported yet.

### Running agents

* `agsekit run <agent_name> [<source_dir>|--vm <vm_name>] [--config <path>] [--disable-backups] [--debug] -- <agent_args...>` — starts an interactive agent command inside Multipass. Environment variables from the config are passed to the process. If a `source_dir` from the mounts list is provided, the agent starts inside the mounted target path in the matching VM; otherwise it launches in the home directory of the default VM. Unless `--disable-backups` is set, background repeated backups for the selected mount are started for the duration of the run. When no backups exist yet, the CLI first creates an initial snapshot with progress output before launching the agent and then starts the repeated loop with the initial run skipped. With `--debug`, the CLI prints every external command before executing it to help troubleshoot agent launches.

### Interactive mode

In a TTY you don’t have to type full commands every time: the CLI can guide you through an interactive menu that fills in parameters for you.

* Run `agsekit` without arguments to open the interactive menu, choose a command, and select options such as the config path, mounts, or agent parameters.
* Start a command without mandatory arguments (for example, `agsekit run`) to automatically fall back to the interactive flow after the CLI prints a “not enough parameters” hint. Use `--non-interactive` if you prefer the usual help output instead of prompts.

## YAML configuration

The configuration file (looked up via `--config`, `CONFIG_PATH`, or `~/.config/agsekit/config.yaml`) describes VM parameters, mounted directories, and any `cloud-init` settings. A base example lives in `config-example.yaml`:

```yaml
vms: # VM parameters for Multipass (you can define several)
  agent-ubuntu: # VM name
    cpu: 2      # number of vCPUs
    ram: 4G     # RAM size (supports 2G, 4096M, etc.)
    disk: 20G   # disk size
    cloud-init: {} # place your standard cloud-init config here if needed
    port-forwarding: # SSH port forwarding applied via multipass ssh when entering the VM
      - type: remote
        host-addr: 127.0.0.1:8080
        vm-addr: 127.0.0.1:80
      - type: local
        host-addr: 0.0.0.0:15432
        vm-addr: 127.0.0.1:5432
      - type: socks5
        vm-addr: 127.0.0.1:8088
mounts:
  - source: /host/path/project            # path to the source folder on the host
    target: /home/ubuntu/project          # mount point inside the VM; defaults to /home/ubuntu/<source_basename>
    backup: /host/backups/project         # backup directory; defaults to backups-<source_basename> next to source
    interval: 5                           # backup interval in minutes; defaults to 5 if omitted
    vm: agent-ubuntu # VM name; defaults to the first VM in the configuration
agents:
  qwen: # agent name; add as many as you need
    type: qwen # agent type: qwen (installs and uses the `qwen` binary), codex, codex-glibc (installs the `codex-glibc` binary), or claude-code (other types are not supported yet)
    env: # arbitrary environment variables passed to the agent process
      OPENAI_API_KEY: "my_local_key"
      OPENAI_BASE_URL: "https://127.0.0.1:11556/v1"
      OPENAI_MODEL: "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
    socks5_proxy: 10.0.0.2:1234 # optional SOCKS5 proxy for the agent traffic via proxychains
    vm: qwen-ubuntu # default VM for this agent; falls back to the mount VM or the first VM in the list
```

> **Note:** Prefer ASCII-only paths for both `source` and `target` mount points: AppArmor may refuse to mount directories whose paths contain non-ASCII characters.

If a VM defines `port-forwarding`, the CLI uses `multipass ssh` with the corresponding `-L`, `-R`, and `-D` flags whenever it enters the VM—for example, when installing agents, starting an agent run, or opening a shell. The example above forwards HTTP from the host to the VM, exposes Postgres from the VM to any host interface, and opens a local SOCKS5 proxy on `127.0.0.1:8088`.


## Backups

### One-off backup

`agsekit backup-once --source-dir <path> --dest-dir <path> [--exclude <pattern> ...] [--progress]` — runs a single backup of the source directory into the specified destination using `rsync`.
The command creates a timestamped directory with a `-partial` suffix, supports incremental copies via `--link-dest` to the previous backup, and honors exclusions from `.backupignore` and `--exclude` arguments. When finished, the temporary folder is renamed to a final timestamp without the suffix. If nothing changed relative to the last backup, no new snapshot is created and the tool reports the absence of updates.

`.backupignore` examples:
```
# exclude virtual environments and dependencies
venv/
node_modules/

# ignore temporary and log files by pattern
*.log
*.tmp

# include a specific file inside an excluded folder
!logs/important.log

# skip documentation build artifacts
docs/build/
```

Backups use `rsync` with incremental links (`--link-dest`) to the previous copy: if only a small set of files changed, the new snapshot stores just the updated data, while unchanged files are hardlinked to the prior snapshot. This keeps a chain of dated directories while consuming minimal space when changes are rare.

### Repeated backups

* `agsekit backup-repeated --source-dir <path> --dest-dir <path> [--exclude <pattern> ...] [--interval <minutes>] [--skip-first]` — runs an immediate backup and then repeats it every `interval` minutes (defaults to five minutes). With `--skip-first`, the loop waits for the first interval before performing the initial run. After each backup it prints `Done, waiting N minutes` with the actual interval value.
* `agsekit backup-repeated-mount --mount <path> [--config <path>]` — looks up the mount by its `source` path in the configuration file (default search: `--config`, `CONFIG_PATH`, `~/.config/agsekit/config.yaml`) and launches repeated backups using the paths and interval from the config. When only one mount is present, `--mount` can be omitted; with multiple mounts, an explicit choice is required.
* `agsekit backup-repeated-all [--config <path>]` — reads all mounts from the config (default search: `--config`, `CONFIG_PATH`, `~/.config/agsekit/config.yaml`) and starts concurrent repeated backups for each entry within a single process. Use Ctrl+C to stop the loops.

### Mount management

* `agsekit mount --source-dir <path> [--config <path>]` — mounts the directory described by `source` in the configuration file (default search: `--config`, `CONFIG_PATH`, `~/.config/agsekit/config.yaml`) into its VM using `multipass mount`. Use `--all` to mount every entry from the config. When there is only one mount in the config, the command can be run without `--source-dir` or `--all`.
* `agsekit umount --source-dir <path> [--config <path>]` — unmounts the directory described by `source` in the config (or `CONFIG_PATH`/`--config`); `--all` unmounts every configured path. If only one mount is configured, the command will unmount it even without explicit flags.

### VM shell access

* `agsekit shell [<vm_name>] [--config <path>]` — opens an interactive `multipass ssh` session inside the chosen VM, applying any configured port forwarding. If only
  one VM is defined in the config, the CLI connects there even without `vm_name`. When several VMs exist and the command runs in
  a TTY, the CLI prompts you to pick one; in non-interactive mode, an explicit `vm_name` is required.

### VM lifecycle

* `agsekit stop <vm_name> [--config <path>]` — stops the specified VM from the configuration. If only one VM is configured, the name can be omitted.
* `agsekit stop --all-vms [--config <path>]` — stops every VM declared in the config file.

### Agent installation

* `agsekit install-agents <agent_name> [<vm>|--all-vms] [--config <path>]` — runs the prepared installation script for the chosen agent type inside the specified VM (or the agent's default VM if none is provided). If the config defines only one agent, you can skip `<agent_name>` and it will be picked automatically.
* `agsekit install-agents --all-agents [--all-vms] [--config <path>]` — installs every configured agent either into their default VM or into every VM when `--all-vms` is set.

The installation scripts live in `agsekit_cli/agent_scripts/`: `codex` installs the npm CLI, `codex-glibc` builds the Rust sources with the glibc target and installs the binary as `codex-glibc`, and `qwen`/`claude-code` follow their upstream steps (the `qwen` script installs the qwen-code CLI). Other agent types are not supported yet.

### Running agents

* `agsekit run <agent_name> [<source_dir>|--vm <vm_name>] [--config <path>] [--disable-backups] [--debug] -- <agent_args...>` — starts an interactive agent command inside Multipass. Environment variables from the config are passed to the process. If a `source_dir` from the mounts list is provided, the agent starts inside the mounted target path in the matching VM; otherwise it launches in the home directory of the default VM. Unless `--disable-backups` is set, background repeated backups for the selected mount are started for the duration of the run. When no backups exist yet, the CLI first creates an initial snapshot with progress output before launching the agent and then starts the repeated loop with the initial run skipped. With `--debug`, the CLI prints every external command before executing it to help troubleshoot agent launches.

### Interactive mode

In a TTY you don’t have to type full commands every time: the CLI can guide you through an interactive menu that fills in parameters for you.

* Run `agsekit` without arguments to open the interactive menu, choose a command, and select options such as the config path, mounts, or agent parameters.
* Start a command without mandatory arguments (for example, `agsekit run`) to automatically fall back to the interactive flow after the CLI prints a “not enough parameters” hint. Use `--non-interactive` if you prefer the usual help output instead of prompts.
