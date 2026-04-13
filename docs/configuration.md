# Configuration

`agsekit` uses a YAML file, usually `~/.config/agsekit/config.yaml`.

Also, in any `agsekit` command you can override the path to the config file when launching:

1. with the command-line argument `--config <path>`
2. with the `CONFIG_PATH` environment variable

## Full Example Config File with Comments:

```yaml
# Global configuration for all of agsekit as a whole
global:
  # Override the folder for ssh keys, default ~/.config/agsekit/ssh. agsekit puts ssh keys here.
  ssh_keys_folder: null
  # Override the env variables folder for the systemd service (used in linux)
  systemd_env_folder: null
  # How often the port forwarding daemon checks configuration, by default every 10 seconds
  portforward_config_check_interval_sec: 10
  # Port range for dynamic allocation when launching a proxy server, default from 48000 to 49000
  http_proxy_port_pool:
    start: 48000
    end: 49000

# Description of virtual machines. At least one is required, any number can be set
vms:
  # VM name, better not change it after creation
  agents-personal:
    # Number of CPU cores
    cpu: 2
    # RAM amount
    ram: 4G
    # Disk size
    disk: 20G
    # Here you can set a full cloud-init configuration for multipass
    cloud-init: {}
    # Enable proxychains for all agents running in this VM and configure it to the specified address
    proxychains: socks5://127.0.0.1:18881
    # Enable port forwarding - forwarding ports into and out of the VM, based on SSH tunnels
    port-forwarding:
      # Types are: remote, local, socks
      # remote means connection from inside the VM to the host
      - type: remote
        host-addr: 127.0.0.1:28881
        vm-addr: 127.0.0.1:18881
      # local means connection from the host into the VM
      - type: local
        host-addr: 127.0.0.1:8080
        vm-addr: 127.0.0.1:80
      # socks5 - open a socks5 proxy port inside the VM leading to the host
      - type: socks5
        vm-addr: 127.0.0.1:11800
    # Install ready "software packages" when creating the VM
    install:
      - docker
      - pyenv
      - python
  # Another VM; in this example there are 2, one for personal projects, the second for work
  agents-nda:
    # Also, cpu, ram, disk amount
    cpu: 2
    ram: 4G
    disk: 20G
    cloud-init: {}
    install:
      - docker
      - pyenv
      - python
    # List of agents that can be run in the VM; the rest cannot. If not specified, everything is allowed.
    allowed_agents: qwen, cline

# Mounting folders into the VM
mounts:
  # source is the path to the folder in the main system
  - source: /home/user/work/work-project-1
    # Backup folder in the main OS; if not specified, it will be set to {folder path}/backups-{folder name}
    backup: /home/user/work/backups-work-project-1
    # Where the folder is mounted inside the VM
    target: /home/ubuntu/work-project-1
    # List of agents that can be run with this folder; the rest cannot. If not specified, all are allowed.
    allowed_agents: [qwen, cline]
    # VM where this folder should be mounted. If not specified, it will be mounted into the FIRST VM from the list
    vm: agents-nda
    # Backup creation interval, in minutes, default 5
    interval: 5
    # Maximum number of backups to keep, default 100
    max_backups: 100
    # Method for cleaning old backups: thin or tail.
    # "thin" - logarithmic thinning (fewer old backups, more fresh ones), storage for greater depth
    # 'tail' - simply delete from the end
    backup_clean_method: thin

# Agent configuration
agents:
  # Agent name can be anything, for example "superagent"; this is what is used when running `agsekit run <agent>`
  qwen:
    # Agent type - one of supported: qwen, codex, claude, cline, aider, forgecode, opencode, codex-glibc, codex-glibc-prebuilt
    type: qwen
    # Environment variables for the agent
    env:
      # Here, for example, a self-hosted model is configured.
      OPENAI_API_KEY: "Your-Api-Key"
      OPENAI_BASE_URL: "http://127.0.0.1:8080"
      OPENAI_MODEL: "Qwen/Qwen3-Coder-9B"
    # In which VM it runs by default if there is no working folder, or it exists in both VMs
    vm: agents-nda
  # Here is an example of an agent of the same type as before, but with a different name
  qwen-cloud:
    type: qwen
    vm: agents-personal
  codex:
    # codex-glibc-prebuilt is a manually built codex agent that supports working through proxychains
    type: codex-glibc-prebuilt
    # The agent can receive default command-line arguments
    default-args:
      - "--sandbox=danger-full-access"
  claude:
    type: claude
    # In the agent, you can override proxychains (empty string disables it)
    proxychains: ""
    # Also, the agent can set http-proxy
    http_proxy: socks5://127.0.0.1:18881

```

## Detailed Description of Each Parameter:

* `global.ssh_keys_folder`
  * Specifies the path to the folder with ssh keys. Commands `agsekit up`, `agsekit prepare` idempotently create ssh keys and add them to the VM for further operation of `agsekit ssh` and `agsekit portforward`.
  * See [prepare](commands/prepare.md) and [networking commands](commands/networking.md)
  * Default: ~/.config/agsekit/ssh
* `global.systemd_env_folder`
  * Specifies the path to the folder with the .env file for launching the systemd service (used only in linux/WSL)
  * See [systemd](commands/systemd.md)
  * Default: ~/.config/agsekit
* `global.portforward_config_check_interval_sec`
  * How often the configuration should be reread so that when the port list changes, SSH tunnels are changed
  * The `agsekit portforward` command and the daemon started through `agsekit systemd start` perform port forwarding, and when the configuration changes, dynamically update ports
  * See [Port Forwarding](networking.md#port-forwarding) and [portforward](commands/networking.md)
* `global.http_proxy_port_pool`
  * Port range from which a port is selected when launching a proxy server
  * The `agsekit run <agent>` command can launch a proxy server if this is set in the configuration or command-line argument, and if it has no listen port, a random one is taken from the range
  * See [HTTP_PROXY](networking.md#httpproxy)
  * Default: `{"start": 48000, "end": 49000}`
* `vms`
  * Set of virtual machines; there can be any number of virtual machines, but at least one
* `vms.<vm_name>`
  * Configuration of a specific virtual machine. Its name is a unique identifier that should not be changed if the VM has already been created, otherwise serious confusion will begin
  * Multipass cannot rename VMs, so the simplest thing if you want to rename one is to destroy the old VM and create a new one.
* `vms.<vm_name>.cpu`
  * Number of processor cores
  * Utilized as the virtual machine uses them
  * At least 2 cores are recommended, but if resources are tight it will somehow work with one
* `vms.<vm_name>.ram`
  * Amount of RAM for the VM
  * Values in Multipass format are allowed, for example `4G` or `4096M`
* `vms.<vm_name>.disk`
  * VM disk size
  * Values in Multipass format are allowed, for example `20G`
* `vms.<vm_name>.cloud-init`
  * Full `cloud-init` configuration passed to `multipass launch` [create-vm / create-vms](commands/create-vm.md)
  * Can be omitted if no additional initial VM setup is needed
* `vms.<vm_name>.proxychains`
  * Proxy URL for launching agents through `proxychains` in this VM, see [Proxychains](networking.md#proxychains)
  * Supported schemes are `http`, `https`, `socks4`, `socks5`
  * An agent can override this value through `agents.<agent_name>.proxychains`; an empty string disables `proxychains`
* `vms.<vm_name>.http_proxy`
  * HTTP proxy for `agsekit run` at VM level, see [HTTP_PROXY](networking.md#httpproxy)
  * Can be a string `scheme://host:port`, then agsekit will start a temporary `privoxy` inside the VM
  * Can be an object `{url: http://host:port}`, then the agent will simply receive `HTTP_PROXY` and `http_proxy`
  * Can be an object `{upstream: scheme://host:port, listen: 127.0.0.1:48080}`, then `privoxy` will listen on the explicitly specified address
  * An agent can override this value through `agents.<agent_name>.http_proxy`
* `vms.<vm_name>.http_proxy.url`
  * Ready HTTP/HTTPS proxy URL for direct mode
  * In this mode `privoxy` is not started
* `vms.<vm_name>.http_proxy.upstream`
  * Upstream proxy for upstream mode through a temporary `privoxy`
  * Supported schemes are `http`, `https`, `socks4`, `socks5`
* `vms.<vm_name>.http_proxy.listen`
  * Address or port on which the temporary `privoxy` will listen inside the VM
  * If only a port is specified, for example `48080`, it turns into `127.0.0.1:48080`
  * If not specified, the port is selected from `global.http_proxy_port_pool`
* `vms.<vm_name>.port-forwarding`
  * List of port forwarding rules for the `agsekit portforward` command
  * Each rule is raised through an SSH tunnel
  * See [Port Forwarding](networking.md#port-forwarding) and [networking commands](commands/networking.md)
* `vms.<vm_name>.port-forwarding[].type`
  * Rule type: `local`, `remote`, or `socks5`
  * `local` opens a port on the host and leads it into the VM
  * `remote` opens a port in the VM and leads it to the host
  * `socks5` opens a SOCKS5 port inside the VM
* `vms.<vm_name>.port-forwarding[].host-addr`
  * Address on the host side in `host:port` format
  * Required for `local` and `remote` rules
  * Not used for `socks5`
* `vms.<vm_name>.port-forwarding[].vm-addr`
  * Address on the VM side in `host:port` format
  * Required for all `port-forwarding` rules
* `vms.<vm_name>.install`
  * List of ready install bundles that will be installed during `create-vm`, `create-vms`, or `up` [create-vm / create-vms](commands/create-vm.md) and [up](commands/up.md)
  * Available bundles:
    * `pyenv` - installs pyenv and dependencies for building Python
    * `nvm` - installs nvm and shell-init hooks
    * `python` - installs pyenv and Python; supports a version, for example `python:3.12.2`
    * `nodejs` - installs nvm and Node.js; supports a version, for example `nodejs:20`
    * `rust` - installs rustup and Rust toolchain
    * `golang` - installs Go toolchain through apt
    * `docker` - installs Docker Engine and Docker Compose through Docker's apt repository
* `vms.<vm_name>.allowed_agents`
  * List of agents that are allowed to run in this VM
  * See [run](commands/run.md)
  * Can be specified as a YAML list or comma-separated string
  * If not specified, the VM-level restriction is not applied
  * The mount restriction has higher priority than the VM restriction
* `mounts`
  * List of host folders that agsekit can mount into the VM
  * Each entry also sets a backup policy for this folder
  * See [mount commands](commands/mount.md)
* `mounts[].source`
  * Path to a folder on the host
  * Required parameter
  * When started from a subfolder, agsekit selects the most exact match by `source`
* `mounts[].backup`
  * Folder on the host where snapshots are placed
  * See [Backups](backups.md)
  * If not specified, `<source_parent>/backups-<source_name>` is used
* `mounts[].target`
  * Path inside the VM where `source` is mounted
  * If not specified, `/home/ubuntu/<source_name>` is used
* `mounts[].allowed_agents`
  * List of agents allowed to work with this folder
  * See [run](commands/run.md)
  * Can be specified as a YAML list or comma-separated string
  * If specified, overrides `vms.<vm_name>.allowed_agents`
* `mounts[].vm`
  * Name of the VM where the folder is mounted
  * If not specified, the first VM from the `vms` section is used
* `mounts[].interval`
  * Repeated backup interval in minutes
  * See [Backups](backups.md)
  * Default: `5`
* `mounts[].max_backups`
  * Maximum number of snapshots for this folder
  * See [Backups](backups.md)
  * Default: `100`
* `mounts[].backup_clean_method`
  * Old backup cleanup method: `thin` or `tail`
  * See [Backups](backups.md)
  * `thin` logarithmically thins history and preserves greater depth
  * `tail` simply deletes the oldest snapshots
  * Default: `thin`
* `agents`
  * Set of agent profiles
  * The profile name is used in the `agsekit run <agent_name>` command
  * See [Supported agents](agents.md)
* `agents.<agent_name>`
  * Configuration of a specific agent
  * The same agent type can be described by several profiles with different settings
* `agents.<agent_name>.type`
  * Agent type
  * See [Supported agents](agents.md)
  * Supported values: `aider`, `qwen`, `forgecode`, `codex`, `opencode`, `codex-glibc`, `codex-glibc-prebuilt`, `claude`, `cline`
  * Required parameter
* `agents.<agent_name>.env`
  * Environment variables that will be passed to the agent process
  * Values are converted to strings; `null` turns into an empty string
* `agents.<agent_name>.default-args`
  * Command-line arguments that agsekit adds when starting the agent
  * See [run](commands/run.md)
  * If the user manually passed an option with the same name, the value from `default-args` is skipped
  * All default-args can be disabled with the flag `agsekit run --skip-default-args <agent>`
* `agents.<agent_name>.vm`
  * One default VM for this agent
  * See [run](commands/run.md)
  * Used when the agent is started outside a mount folder and the VM is not selected through the `--vm` argument
  * Default is the first VM in the list (if this agent is allowed in it)
* `agents.<agent_name>.vms`
  * List of VMs to which the agent is bound; used not for launch restrictions, but for install-agents / status commands
  * See [install-agents](commands/install-agents.md) and [status](commands/status.md)
  * Can be specified as a YAML list or comma-separated string
  * By default, all VMs are considered to be here
* `agents.<agent_name>.proxychains`
  * Proxychains setting for a specific agent
  * See [Proxychains](networking.md#proxychains)
  * Overrides `vms.<vm_name>.proxychains`
  * Empty string disables `proxychains` for the agent
* `agents.<agent_name>.http_proxy`
  * HTTP proxy for a specific agent
  * See [HTTP_PROXY](networking.md#httpproxy)
  * Format is the same as `vms.<vm_name>.http_proxy`
  * Overrides `vms.<vm_name>.http_proxy`; empty string disables `http_proxy` for the agent
* `agents.<agent_name>.http_proxy.url`
  * Ready HTTP/HTTPS proxy URL for direct mode
  * The agent receives `HTTP_PROXY` and `http_proxy` variables
* `agents.<agent_name>.http_proxy.upstream`
  * Upstream proxy for upstream mode through a temporary `privoxy`
  * Supported schemes are `http`, `https`, `socks4`, `socks5`
* `agents.<agent_name>.http_proxy.listen`
  * Address or port of the temporary `privoxy` inside the VM
  * If not specified, the port is selected from `global.http_proxy_port_pool`
