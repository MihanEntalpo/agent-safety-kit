# Getting Started

This page is the shortest practical route to a working `agsekit` setup.

## 1. Install

Create a virtual environment and install the package:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install agsekit
```

Host-side Multipass installation is handled later by `agsekit prepare` or `agsekit up`.

## 2. Create a Config

Recommended:

```bash
agsekit config-gen
```

Alternative:

```bash
agsekit config-example
```

Then edit `~/.config/agsekit/config.yaml` or pass a custom path with `--config`.

## 3. Prepare the Environment

Bring up the full environment:

```bash
agsekit up
```

This can include:

- host dependency preparation;
- VM creation;
- VM preparation;
- agent installation;
- Linux-only systemd setup for `portforward`.

## 4. Add a Mount

Add your project directory:

```bash
agsekit addmount /path/to/project
```

The CLI can choose sensible defaults for VM path, backup path, interval, and cleanup policy.

## 5. Run an Agent

Enter the project directory and launch an agent:

```bash
cd /path/to/project
agsekit run qwen
```

If backups are enabled and no snapshot exists yet, the first run creates an initial backup before the agent starts.

## 6. Inspect State

Useful commands after setup:

```bash
agsekit status
agsekit shell
agsekit ssh agent-ubuntu
```

## See Also

- [Configuration reference](configuration.md)
- [Supported agents](agents.md)
- [Networking](networking.md)
- [Command index](commands/README.md)
