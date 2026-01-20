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

- Agents run only inside a virtual machine.
- The VM is launched via Multipass (a simple Canonical tool to start Ubuntu VMs with a single command).
- Project folders from the host are mounted into the VM; an automatic backup job runs in parallel to a sibling directory at a configurable interval (defaults to every five minutes and only when changes are detected), using `rsync` with hardlinks to save space.
- VM, mount, and cloud-init settings are stored in a YAML config.
- You can run the agent without entering the guest via `multipass shell`—it still executes inside the VM.
- Multipass commands and agent runs can be wrapped in proxychains: set a proxy URL per VM or override it once with `--proxychains` to generate a temporary proxychains config automatically.

## Working agents

Currently confirmed working agent types are:

- qwen
- codex
- codex-glibc (built dynamically)

## Quick start

1. Install the package with pip (requires Python 3.9 or newer):
   ```bash
   python3 -m venv ./venv
   source ./venv/bin/activate
   pip install agsekit
   ```
   This makes the `agsekit` command available inside the virtual environment.

2. Alternatively, clone the repository and install from sources:
   ```bash
   git clone https://github.com/MihanEntalpo/agent-safety-kit/
   cd agent-safety-kit
   pip install .
   ```

3. Create a YAML configuration (the CLI checks `--config`, then `CONFIG_PATH`, then `~/.config/agsekit/config.yaml`):
   ```bash
   agsekit config-example
   # edit vms/mounts/cloud-init to your needs
   ```
   When working from a cloned repository, you can also copy the file directly:
   ```bash
   mkdir -p ~/.config/agsekit
   cp config-example.yaml ~/.config/agsekit/config.yaml
   ```
   You can also run `agsekit config-gen` to answer a few questions and save the config (defaults to `~/.config/agsekit/config.yaml`; use `--overwrite` to replace an existing file).

4. Install required system dependencies (in particular, Multipass; requires sudo and currently works only on Debian-based systems). The command also creates the host SSH keypair used for VM access:
   ```bash
   agsekit prepare
   ```

5. Create the virtual machines defined in YAML (this also installs VM packages and syncs SSH keys into each VM):
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

* `agsekit prepare` — installs required system dependencies (including Multipass; requires sudo and currently works only on Debian-based systems) and creates the SSH keypair used to access VMs.
* `agsekit config-gen [--config <path>] [--overwrite]` — interactive wizard that asks about VMs, mounts, and agents, then writes a YAML config to the chosen path (defaults to `~/.config/agsekit/config.yaml`). Without `--overwrite`, the command warns if the file already exists.
* `agsekit config-example [<path>]` — copies `config-example.yaml` to the target path (defaults to `~/.config/agsekit/config.yaml`). If the default config already exists, the command skips copying.
* `agsekit pip-upgrade` — upgrades agsekit using `pip install agsekit --upgrade` inside the same Python environment that runs the CLI. If agsekit is not installed in that environment via pip, the command reports that it cannot be upgraded there.
* `agsekit create-vms` — creates every VM defined in the YAML configuration and prepares them (installs packages and syncs SSH keys).
* `agsekit create-vm <name>` — launches just one VM and prepares it (installs packages and syncs SSH keys). If the config contains only one VM, you can omit `<name>` and it will be used automatically. If a VM already exists, the command compares the desired resources with the current ones and reports any differences. Changing resources of an existing VM is not supported yet.
* `agsekit shell [<vm_name>] [--config <path>]` — opens an interactive `multipass shell` session inside the chosen VM, applying any configured port forwarding. If only
  one VM is defined in the config, the CLI connects there even without `vm_name`. When multiple VMs exist and the command runs in
  a TTY, the CLI prompts you to pick one; in non-interactive mode, an explicit `vm_name` is required.
* `agsekit ssh <vm_name> [--config <path>] [<ssh_args...>]` — connects to the VM over SSH using `~/.config/agsekit/ssh/id_rsa` and forwards any extra arguments directly to the `ssh` command (for example, `-L`, `-R`, `-N`).
* `agsekit portforward [--config <path>]` — starts a dedicated `agsekit ssh` tunnel for each VM that defines `port-forwarding` rules, monitoring the child processes and restarting them if they exit. Stop with Ctrl+C to gracefully terminate the tunnels.
* `agsekit start-vm <vm_name> [--config <path>]` — starts the specified VM from the configuration. If only one VM is configured, the name can be omitted.
* `agsekit start-vm --all-vms [--config <path>]` — starts every VM declared in the config file.
* `agsekit stop-vm <vm_name> [--config <path>]` — stops the specified VM from the configuration. If only one VM is configured, the name can be omitted.
* `agsekit stop-vm --all-vms [--config <path>]` — stops every VM declared in the config file.
* `agsekit destroy-vm <vm_name> [--config <path>] [-y]` — deletes the specified VM from Multipass. Without `-y`, the CLI asks for interactive confirmation.
* `agsekit destroy-vm --all [--config <path>] [-y]` — deletes every VM from the configuration, with the same confirmation requirement.
* `agsekit systemd install [--config <path>]` — writes `~/.config/agsekit/systemd.env` with absolute paths to `agsekit`, the config, and the current project directory, then registers and starts the user unit from `systemd/agsekit-portforward.service` via `systemctl --user` (link, daemon-reload, start, enable).
* `agsekit systemd uninstall` — stops and disables the user unit, then removes the linked `systemd/agsekit-portforward.service` from systemd via `systemctl --user`.

### Mount management

* `agsekit mount --source-dir <path> [--config <path>]` — mounts the directory described by `source` in the configuration file (default search: `--config`, `CONFIG_PATH`, `~/.config/agsekit/config.yaml`) into its VM using `multipass mount`. Use `--all` to mount every entry from the config. When there is only one mount in the config, the command can be run without `--source-dir` or `--all`.
* `agsekit umount --source-dir <path> [--config <path>]` — unmounts the directory described by `source` in the config (or `CONFIG_PATH`/`--config`); `--all` unmounts every configured path. If only one mount is configured, the command will unmount it even without explicit flags.
* `agsekit addmount <path> [<vm_path> <backup_path> <interval>] [--max-backups <count>] [--backup-clean-method <tail|thin>] [--config <path>] [--mount] [-y]` — adds a mount entry to the YAML config (located via `--config`, `CONFIG_PATH`, or `~/.config/agsekit/config.yaml`). If `<path>` is omitted, the command enters interactive mode and asks for the host path. The VM path defaults to `/home/ubuntu/<folder_name>`, the backup path defaults to `<parent_dir>/backups-<folder_name>`, the backup interval defaults to five minutes, the retention cap defaults to 100 snapshots, and the cleanup method defaults to `thin`. Before saving, the CLI prints the parameters and asks for confirmation unless `-y` is provided; it also stores a timestamped backup of the config file while preserving comments. Use `--mount` to mount the new entry immediately after saving (interactive mode also asks whether to mount right away).
* `agsekit removemount [<path>] [--config <path>] [--vm <vm_name>] [-y]` — removes a mount entry from the YAML config (located via `--config`, `CONFIG_PATH`, or `~/.config/agsekit/config.yaml`). If `<path>` is omitted, the command prompts to select one of the configured mounts. When multiple mounts share the same source path, use `--vm` to disambiguate. Before saving, the CLI prints the selected mount and asks for confirmation unless `-y` is provided; it also stores a timestamped backup of the config file while preserving comments. The CLI always unmounts the entry first; if unmounting fails, the config is left untouched.

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

* `agsekit backup-repeated --source-dir <path> --dest-dir <path> [--exclude <pattern> ...] [--interval <minutes>] [--max-backups <count>] [--backup-clean-method <tail|thin>] [--skip-first]` — runs an immediate backup and then repeats it every `interval` minutes (defaults to five minutes). With `--skip-first`, the loop waits for the first interval before performing the initial run. After each backup it prints `Done, waiting N minutes` with the actual interval value.
* `agsekit backup-repeated-mount --mount <path> [--config <path>]` — looks up the mount by its `source` path in the configuration file (default search: `--config`, `CONFIG_PATH`, `~/.config/agsekit/config.yaml`) and launches repeated backups using the paths and interval from the config. When only one mount is present, `--mount` can be omitted; with multiple mounts, an explicit choice is required.
* `agsekit backup-repeated-all [--config <path>]` — reads all mounts from the config (default search: `--config`, `CONFIG_PATH`, `~/.config/agsekit/config.yaml`) and starts concurrent repeated backups for each entry within a single process. Use Ctrl+C to stop the loops.

#### Backup cleanup

* `agsekit backup-clean <mount_source> [<keep>] [<method>] [--config <path>]` — removes old snapshots from the backup directory for the mount whose `source` matches `<mount_source>` in the config (default search: `--config`, `CONFIG_PATH`, `~/.config/agsekit/config.yaml`). `<keep>` defaults to 50 and controls how many of the newest backups remain. `<method>` defaults to `thin` for logarithmic thinning: it keeps the latest three backups within the most recent intervals and then thins older snapshots so the further in the past they are, the more sparse they become.

### Agent installation

* `agsekit install-agents <agent_name> [<vm>|--all-vms] [--config <path>] [--proxychains <value>]` — runs the prepared installation script for the chosen agent type inside the specified VM (or the agent's default VM if none is provided). If the config defines only one agent, you can skip `<agent_name>` and it will be picked automatically. Use `--proxychains <scheme://host:port>` to override the VM proxy for this installation or `--proxychains ""` to ignore it once.
* `agsekit install-agents --all-agents [--all-vms] [--config <path>] [--proxychains <value>]` — installs every configured agent either into their default VM or into every VM when `--all-vms` is set.

The installation scripts live in `agsekit_cli/agent_scripts/`: `codex` installs the npm CLI, `codex-glibc` builds the Rust sources with the glibc target and installs the binary as `codex-glibc`, and `qwen`/`claude-code` follow their upstream steps (the `qwen` script installs the qwen-code CLI). Other agent types are not supported yet.

### Running agents

* `agsekit run <agent_name> [<source_dir>|--vm <vm_name>] [--config <path>] [--proxychains <value>] [--disable-backups] [--skip-default-args] [--debug] -- <agent_args...>` — starts an interactive agent command inside Multipass. Environment variables from the config are passed to the process. If a `source_dir` from the mounts list is provided, the agent starts inside the mounted target path in the matching VM; otherwise it launches in the home directory of the default VM. Unless `--disable-backups` is set, background repeated backups for the selected mount are started for the duration of the run. When no backups exist yet, the CLI first creates an initial snapshot with progress output before launching the agent and then starts the repeated loop with the initial run skipped. Arguments from `agents.<name>.default-args` are added unless `--skip-default-args` is set; if the user already passed an option with the same name (for example `--openai-api-key`), the default value is skipped. With `--debug`, the CLI prints every external command before executing it to help troubleshoot agent launches. Use `--proxychains <scheme://host:port>` to override the VM setting for one run; pass an empty string to disable it temporarily.

### Interactive mode

In a TTY you don’t have to type full commands every time: the CLI can guide you through an interactive menu that fills in parameters for you.

* Run `agsekit` without arguments to open the interactive menu, choose a command, and select options such as the config path, mounts, or agent parameters.
* Start a command without mandatory arguments (for example, `agsekit run`) to automatically fall back to the interactive flow after the CLI prints a “not enough parameters” hint. Use `--non-interactive` if you prefer the usual help output instead of prompts.

## Localization

The CLI reads the system locale and falls back to English if it cannot detect a supported language. You can override this behavior with the `AGSEKIT_LANG` environment variable:

```bash
AGSEKIT_LANG=ru agsekit --help
```

## YAML configuration

The configuration file (looked up via `--config`, `CONFIG_PATH`, or `~/.config/agsekit/config.yaml`) describes VM parameters, mounted directories, and any `cloud-init` settings. A base example lives in `config-example.yaml`:

```yaml
vms: # VM parameters for Multipass (you can define multiple)
  agent-ubuntu: # VM name
    cpu: 2      # number of vCPUs
    ram: 4G     # RAM size (supports 2G, 4096M, etc.)
    disk: 20G   # disk size
    proxychains: "" # optional proxy URL (scheme://host:port); agsekit writes a temporary proxychains.conf and wraps Multipass commands automatically
    cloud-init: {} # place your standard cloud-init config here if needed
    port-forwarding: # Port forwarding config
      - type: remote # Open port inside VM and pass connections to Host machine's port
        host-addr: 127.0.0.1:80
        vm-addr: 127.0.0.1:8080
      - type: local # Open port on Host machine, and pass connections to VM's port
        host-addr: 0.0.0.0:15432
        vm-addr: 127.0.0.1:5432
      - type: socks5 # Open socks5-proxy port inside VM, directing traffic to Host machine's network
        vm-addr: 127.0.0.1:8088        
    install: # install bundles executed during create-vm/create-vms
      - python        # pyenv + latest stable Python
      - nodejs:20     # nvm + Node.js 20
      - rust          # rustup + toolchain
mounts:
  - source: /host/path/project            # path to the source folder on the host
    target: /home/ubuntu/project          # mount point inside the VM; defaults to /home/ubuntu/<source_basename>
    backup: /host/backups/project         # backup directory; defaults to backups-<source_basename> next to source
    interval: 5                           # backup interval in minutes; defaults to 5 if omitted
    max_backups: 100                      # number of snapshots to keep after cleanup; defaults to 100
    backup_clean_method: tail             # cleanup method after each backup: tail or thin; defaults to tail
    vm: agent-ubuntu # VM name; defaults to the first VM in the configuration
agents:
  qwen: # agent name; add as many as you need
    type: qwen # agent type: qwen (installs and uses the `qwen` binary), codex, codex-glibc (installs the `codex-glibc` binary), or claude-code (other types are not supported yet)
    env: # arbitrary environment variables passed to the agent process
      OPENAI_API_KEY: "my_local_key"
      OPENAI_BASE_URL: "https://127.0.0.1:11556/v1"
      OPENAI_MODEL: "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
    default-args: # arguments passed to the agent unless the user overrides them
      - "--openai-api-key=my_local_key"
      - "--openai-base-url=https://127.0.0.1:11556/v1"
    vm: qwen-ubuntu # default VM for this agent; falls back to the mount VM or the first VM in the list
  codex:
    type: codex 
  claude:
    type: claude-code
  codex2:
    type: codex-glibc
```

### VM install bundles

Each VM can define an `install` list of bundles to be installed during `agsekit create-vm` / `create-vms`. Bundles are implemented as idempotent bash scripts and can depend on each other (for example, `python` installs `pyenv` first). Names can include a version suffix after `:` when supported. Supported bundles:

* `pyenv` — installs pyenv along with build dependencies, and wires it into `~/.profile`, `~/.bashrc`, and `~/.bash_profile`.
* `nvm` — installs nvm and wires it into `~/.profile`, `~/.bashrc`, and `~/.bash_profile`.
* `python` — installs pyenv plus the latest stable Python.
* `python:<version>` — installs pyenv plus the specified Python version (for example, `python:3.12.4`).
* `nodejs` — installs nvm plus the latest LTS Node.js.
* `nodejs:<version>` — installs nvm plus the specified Node.js version (for example, `nodejs:20`).
* `rust` — installs rustup with the Rust toolchain.
* `golang` — installs the Go toolchain via apt.
* `docker` — installs Docker Engine and Docker Compose via Docker's apt repository.

Run `agsekit list-bundles` to see the up-to-date bundle list and descriptions.

> **Note:** Prefer ASCII-only paths for both `source` and `target` mount points: AppArmor may refuse to mount directories whose paths contain non-ASCII characters.
