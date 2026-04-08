# Agent Safety Kit

Want to run Claude Code, Codex, and other coding agents, but fully understand how bad that can get on your main workstation?

This project is for people who do not want to turn their laptop into a live-fire exercise in code destruction, secret leakage, and digital self-sabotage.

[Documentation index](docs/README.md) | [Русская документация](docs-ru/README.md) | [Project philosophy](philosophy.md)

## Why this matters

Autonomous coding agents can feel like magic. But this is exactly the kind of magic that can make your repository, local state, credentials, and private data disappear in one spectacularly bad session.

On the websites of both AI giants and small agent vendors, installation often looks like harmless `curl | bash`, `npm i -g ...`, and then `<agent_name>`. Behind that convenience sits a much harsher statement: you are allowing untrusted code execution on your working machine.

Some of the more serious failure modes and warnings:

- [A prompt injection can redirect an AI agent to execute an attacker's instructions on your machine](https://arxiv.org/abs/2507.20526)
- [Claude Code escapes its own denylist and sandbox protections](https://ona.com/stories/how-claude-code-escapes-its-own-denylist-and-sandbox)
- [Qwen Coder agent destroys working builds](https://github.com/QwenLM/qwen-code/issues/354)
- [Codex keeps deleting unrelated and uncommitted files](https://github.com/openai/codex/issues/4969)
- [Claude Code deleted my entire workspace](https://www.reddit.com/r/ClaudeAI/comments/1m299f5/claude_code_deleted_my_entire_workspace_heres_the/)
- [I Asked Claude Code to Fix All Bugs, and It Deleted the Whole Repo](https://levelup.gitconnected.com/i-asked-claude-code-to-fix-all-bugs-and-it-deleted-the-whole-repo-e7f24f5390c5)

People keep saying “just make backups” and “just use git”, but that misses the actual threat surface:

- agents destroy unstaged changes;
- agents can break out of the project boundary and damage files elsewhere in your OS;
- agents can read beyond the project tree and may exfiltrate private SSH keys or other secrets after consuming a prompt injection from docs, issue trackers, or hostile code;
- agents may benefit from kernel or local privilege escalation paths if you hand them enough tools and enough trust;
- even without malice, an agent can hallucinate, delete a “broken” project instead of fixing it, or wipe a database and its backups because it confidently chose the wrong recovery action.

Modern coding agents already perform at a high level on offensive-security-style tasks. If you give one too much access, a network connection, and a bad objective, the damage radius can extend far beyond a single repository. `agsekit` exists because treating that risk as theoretical is reckless.

## Architecture

Placeholder: architecture diagram goes here.

The system is built around a simple loop:

- The host machine keeps the real source tree and launches Ubuntu VMs through Multipass.
- A project folder is mounted from the host into a chosen VM.
- The agent binary runs inside the VM, not on the host.
- `agsekit` runs repeated incremental backups of the mounted host folder while the agent session is active.
- Optional `proxychains`, `http_proxy`, and `portforward` features handle restricted-network setups.

See [docs/architecture.md](docs/architecture.md) for the full model.

## Demo

Placeholder: terminal GIF / screencast goes here.

Suggested demo flow:

1. Generate a config.
2. Bring up a VM with `agsekit up`.
3. Add a mount.
4. Launch an agent with `agsekit run`.
5. Show backup snapshots being created in parallel.

## Quick Start

Install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install agsekit
```

Generate a config:

```bash
agsekit config-gen
```

Prepare everything:

```bash
agsekit up
```

Add your project as a mount:

```bash
agsekit addmount /path/to/project
```

Run an agent from the mounted project directory:

```bash
cd /path/to/project
agsekit run qwen
```

Detailed setup lives in [docs/getting-started.md](docs/getting-started.md).

## Features

- Run agents inside a Multipass VM instead of directly on the host.
- Keep mounts, VM definitions, networking, and agent defaults in declarative YAML.
- Create automatic incremental backups with hardlink-based snapshots.
- Install supported agent CLIs into target VMs with `install-agents`.
- Use `proxychains` for agent installation and runtime commands.
- Use VM-level or agent-level `http_proxy` settings.
- Keep SSH port forwarding alive with `agsekit portforward`.
- Mix interactive and non-interactive CLI workflows.
- Prepare Linux and macOS hosts automatically.

## Documentation

- [Documentation index](docs/README.md)
- [Getting started](docs/getting-started.md)
- [How-to recipes](docs/how-to.md)
- [Architecture](docs/architecture.md)
- [Configuration reference](docs/configuration.md)
- [Agents](docs/agents.md)
- [Networking and proxies](docs/networking.md)
- [Backups](docs/backups.md)
- [Command reference](docs/commands/README.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Known issues](docs/known-issues.md)

## Supported Agents

- [aider](https://aider.chat/)
- [Qwen Code](https://qwenlm.github.io/qwen-code-docs/en/)
- [ForgeCode](https://forgecode.dev/)
- [Codex](https://openai.com/codex/)
- [OpenCode](https://opencode.ai/)
- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- [Cline](https://cline.bot/)
- `codex-glibc` — `agsekit` variant of [Codex](https://openai.com/codex/)
- `codex-glibc-prebuilt` — `agsekit` variant of [Codex](https://openai.com/codex/)

See [docs/agents.md](docs/agents.md) for installation and runtime notes.

## Security Model and Limitations

What this tool does:

- isolates agent execution inside a VM;
- keeps the host project in mounted storage;
- creates rollback-friendly backups around agent runs.

What this tool does not do:

- guarantee sandbox safety inside the guest VM;
- prevent bad edits inside the mounted project;
- replace code review, git hygiene, or secrets discipline.

More context: [philosophy.md](philosophy.md)

## Platform Support

- Linux host: supported
- macOS host: supported for Multipass-based workflows
- Windows host: not a first-class workflow yet
- Guest OS: Ubuntu via Multipass

## FAQ

### Who is this for?

Developers who want to experiment with coding agents but want isolation and rollback points.

### Is git still required?

Yes. `agsekit` complements git; it does not replace it.

### Why Multipass instead of Docker?

The project targets a full Ubuntu VM workflow with SSH, mounts, port forwards, and agent installers that behave like a normal Linux machine.

## Contributing and License

- Contributing guidance will grow under `docs/`.
- License: [LICENSE](LICENSE)
