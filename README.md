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
- You can run the agent without entering the guest via `multipass shell`—it still executes inside the VM.

## Quick start

1. Clone the repository and enter it:
   ```bash
   git clone https://github.com/MihanEntalpo/agent-safety-kit/
   cd agent-safety-kit
   ```

2. Set up the Python environment and dependencies (requires Python 3.10 or newer):
   ```bash
   python3 -m venv ./venv
   source ./venv/bin/activate
   pip install -r requirements.txt
   ```

3. Create a YAML configuration (defaults to `config.yaml`; override with `CONFIG_PATH` if needed):
   ```bash
   cp config-example.yaml config.yaml
   # edit vms/mounts/cloud-init to your needs
   ```

4. Install required system dependencies (in particular, Multipass; requires sudo and currently works only on Debian-based systems):
   ```bash
   ./agsekit prepare
   ```

5. Create the virtual machines defined in YAML:
   ```bash
   ./agsekit create-vms
   ```

   To launch just one VM, use `./agsekit create-vm <name>`. If a VM already exists, the command compares the desired resources with the current ones and reports any differences. Changing resources of an existing VM is not supported yet.

6. Mount your folders (assuming mounts are already configured in the YAML file):
   ```bash
   ./agsekit mount --all
   ```

7. Install all configured agents into their default VMs:
   ```bash
   ./agsekit setup-agents --all-agents
   ```

8. (Optional) Start repeated backups for every configured mount to validate the setup:
   ```bash
   ./agsekit backup-repeated-all --config config.yaml
   ```

9. Launch an agent inside its VM (example runs `qwen` inside its mount with backups enabled by default):
   ```bash
   ./agsekit run qwen /host/path/project --vm agent-ubuntu --config config.yaml -- --help
   ```

## YAML configuration

`config.yaml` (or the path from `CONFIG_PATH`) describes VM parameters, mounted directories, and any `cloud-init` settings. A base example lives in `config-example.yaml`:

```yaml
vms: # VM parameters for Multipass (you can define several)
  agent-ubuntu: # VM name
    cpu: 2      # number of vCPUs
    ram: 4G     # RAM size (supports 2G, 4096M, etc.)
    disk: 20G   # disk size
    cloud-init: {} # place your standard cloud-init config here if needed
mounts:
  - source: /host/path/project            # path to the source folder on the host
    target: /home/ubuntu/project          # mount point inside the VM; defaults to /home/ubuntu/<source_basename>
    backup: /host/backups/project         # backup directory; defaults to backups-<source_basename> next to source
    interval: 5                           # backup interval in minutes; defaults to 5 if omitted
    vm: agent-ubuntu # VM name; defaults to the first VM in the configuration
agents:
  qwen: # agent name; add as many as you need
    type: qwen-code # agent type: qwen-code (uses the `qwen` binary), codex-cli, or claude-code (other types are not supported yet)
    env: # arbitrary environment variables passed to the agent process
      OPENAI_API_KEY: "my_local_key"
      OPENAI_BASE_URL: "https://127.0.0.1:11556/v1"
      OPENAI_MODEL: "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
    socks5_proxy: 10.0.0.2:1234 # optional SOCKS5 proxy for the agent traffic via proxychains
    vm: qwen-ubuntu # default VM for this agent; falls back to the mount VM or the first VM in the list
```


## Backups

### One-off backup

`./agsekit backup-once --source-dir <path> --dest-dir <path> [--exclude <pattern> ...]` — runs a single backup of the source directory into the specified destination using `rsync`.
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

* `./agsekit backup-repeated --source-dir <path> --dest-dir <path> [--exclude <pattern> ...] [--interval <minutes>]` — runs an immediate backup and then repeats it every `interval` minutes (defaults to five minutes). After each run it prints `Done, waiting N minutes` with the actual interval value.
* `./agsekit backup-repeated-mount --mount <path> [--config <path>]` — looks up the mount by its `source` path in `config.yaml` (or the path from `CONFIG_PATH`/`--config`) and launches repeated backups using the paths and interval from the config. Fails if the mount is missing.
* `./agsekit backup-repeated-all [--config <path>]` — reads all mounts from the config (defaults to `config.yaml` or the path from `CONFIG_PATH`/`--config`) and starts concurrent repeated backups for each entry within a single process. Use Ctrl+C to stop the loops.

### Mount management

* `./agsekit mount --source-dir <path> [--config <path>]` — mounts the directory described by `source` in `config.yaml` (or the path from `CONFIG_PATH`/`--config`) into its VM using `multipass mount`. Use `--all` to mount every entry from the config.
* `./agsekit umount --source-dir <path> [--config <path>]` — unmounts the directory described by `source` in the config (or `CONFIG_PATH`/`--config`); `--all` unmounts every configured path.

### Agent installation

* `./agsekit setup-agents <agent_name> [<vm>|--all-vms] [--config <path>]` — runs the prepared installation script for the chosen agent type inside the specified VM (or the agent's default VM if none is provided).
* `./agsekit setup-agents --all-agents [--all-vms] [--config <path>]` — installs every configured agent either into their default VM or into every VM when `--all-vms` is set.

The installation scripts live in `agsekit_cli/agent_scripts/` and mirror the standard setup steps for codex-cli, qwen-code, and claude-code. Other agent types are not supported yet.

### Running agents

* `./agsekit run <agent_name> [<source_dir>|--vm <vm_name>] [--config <path>] [--disable-backups] [--debug] -- <agent_args...>` — starts an interactive agent command inside Multipass. Environment variables from the config are passed to the process. If a `source_dir` from the mounts list is provided, the agent starts inside the mounted target path in the matching VM; otherwise it launches in the home directory of the default VM. Unless `--disable-backups` is set, background repeated backups for the selected mount are started for the duration of the run. With `--debug`, the CLI prints every external command before executing it to help troubleshoot agent launches.

### Interactive mode

In a TTY you don’t have to type full commands every time: the CLI can guide you through an interactive menu that fills in parameters for you.

* Run `./agsekit` without arguments to open the interactive menu, choose a command, and select options such as the config path, mounts, or agent parameters.
* Start a command without mandatory arguments (for example, `./agsekit run`) to automatically fall back to the interactive flow after the CLI prints a “not enough parameters” hint. Use `--non-interactive` if you prefer the usual help output instead of prompts.
