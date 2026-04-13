# Agent Safety Kit

Want to run Claude Code, Codex, and other AI agents for development, but do not want them to delete your project, break your system, or hand your secrets to third parties?

This project gives you a convenient toolkit for running AI agents in a virtual machine almost the same way as "normally".

[Documentation index](docs/README.md) | [Русская документация](docs-ru/README.md) | [Project philosophy](philosophy.md)

## Why?

The way autonomous AI agents work feels like magic. But then an agent goes "whoosh" and, as if by magic, the project disappears, the local environment is damaged, the database is wiped, private keys are compromised, and in general everything the agent can reach is at risk.

On the websites of both giant corporations and small teams building their own AI agents, installation often looks like `curl | bash`, `npm i -g ...`, and then `<agent_name>`.

In practice, this is a two-command way to allow arbitrary code execution on your working machine, while trusting security to people who, if something happens, will not be responsible for the consequences.

A few stories for illustration:

- [Research: AI agents can swallow a prompt injection and start carrying out someone else's will on your PC](https://arxiv.org/abs/2507.20526)
- [Claude Code bypasses its own protections and escapes the sandbox](https://ona.com/stories/how-claude-code-escapes-its-own-denylist-and-sandbox)
- [Qwen Coder breaks working builds](https://github.com/QwenLM/qwen-code/issues/354)
- [Codex keeps deleting files that are not added to git and are unrelated to the task](https://github.com/openai/codex/issues/4969)
- [Claude Code deleted my entire working environment](https://www.reddit.com/r/ClaudeAI/comments/1m299f5/claude_code_deleted_my_entire_workspace_heres_the/)
- [I asked Claude Code to fix all bugs, and it just deleted my project](https://levelup.gitconnected.com/i-asked-claude-code-to-fix-all-bugs-and-it-deleted-the-whole-repo-e7f24f5390c5)
- [Claude Code deleted 25,000 documents from a third-party project while I was distracted](https://www.reddit.com/r/ClaudeAI/comments/1rshuz9/an_ai_agent_deleted_25000_documents_from_the/)

Other stories can be found in unlimited quantities on Google with the query: [coding agent deleted|removed|compromised|destroyed](https://www.google.com/search?q=coding+agent+deleted%7Cremoved%7Ccompromised%7Cdestroyed)

Everywhere people write: "just make backups", "just use git".

But that is not enough:

- agents destroy unstaged changes, and git will not help here;
- agents leave the project folder and their own sandbox and can damage files in your OS;
- agents can read outside the project folder and potentially read and send your private SSH keys or other secrets to an attacker after eating a prompt injection somewhere on a documentation page, in an issue tracker, or in an infected project;
- agents can use vulnerabilities in the kernel or local environment if you give them too many rights, tools, and trust;
- even with the best intentions, an agent can hallucinate nonexistent information, delete a "broken" project instead of fixing it, bring down a DB and wipe its backups, simply because it confidently chose the wrong action.

Modern coding agents already show a very high level on tasks related to finding and exploiting vulnerabilities. If you give such an agent broad access, the blast radius can easily go far beyond one repository.

Another idea is to run agents in docker/podman/lxc. It is quite reasonable, but it also has downsides:

- a container is different from a full PC that agents are designed for, which creates a number of limits. The simplest one is that safely running nested Docker inside Docker is difficult, and this matters in modern development.
- a container provides much weaker isolation from a malicious agent that has eaten prompt injections somewhere. Escaping a container via kernel vulnerabilities is easier than escaping a VM.

## Quick Start

Working with an agent through agsekit is not much harder than working with a "bare" agent.

Of course, you need to do the initial setup, but it is much simpler than doing everything manually: installing a VM, connecting to it, installing software, and so on.

1. Installation (you need Python 3.9+). Deb/Arch Linux, macOS (with Homebrew), and Windows (through WSL) are supported.

If you are lazy and fearless:

```shell
curl -fsSL https://agsekit.org/install.sh | sh
```

If you want to do everything yourself, or the "lazy" way did not work:

[Detailed installation guide](./docs/install.md)

2. Create a configuration through the interactive setup wizard:

```shell
agsekit config-gen
```

If you want, you can copy the config template and edit it manually:

```shell
agsekit config-example
nano ~/.config/agsekit/config.yaml
```

[Detailed configuration guide](./docs/configuration.md)

3. Initial installation and setup of everything:

```shell
agsekit up
```

This command installs Multipass, creates a virtual machine, installs agents, and installs software packages.

It may take some time.

4. Add a project folder:

```shell
agsekit addmount ~/project/my-project
```

An interactive mode will start and ask a number of questions. You can answer them by simply pressing ENTER.

5. Run the agent in the project folder:

Assume you configured an agent named claude:

```shell
cd ~/project/my-project
agsekit run claude
```

That is it, you can use it.

More details: [Getting started](docs/getting-started.md)

## How It Works

* agsekit is a CLI tool for simplifying work with agents in virtual machines
* the simple and convenient Multipass is used as the virtual machine engine
* the agent runs inside a Multipass VM (with Ubuntu installed in it)
* to work with the project, its folder is mounted into the VM
* so the agent cannot cause damage by wiping the mounted project folder, cyclic backup of the project folder on the main machine runs at the same time as the agent
* if the agent needs internet access through an http-proxy or socks-proxy, there is support for http-proxy through proxify and running through proxychains4
* ports can be conveniently forwarded into and out of the VM (based on SSH tunnels)
* you can have several VMs for different purposes, for example one for personal projects and another for work under NDA
* there is a set of basic supported agents, and also different software bundles installed into the VM with one command

**The basic workflow is this:**

- The host machine stores the real source code and launches an Ubuntu VM through Multipass.
- The project folder is mounted from the host into the selected VM.
- The agent binary runs inside the VM, not on the host.
- `agsekit` runs repeated incremental backups of the mounted folder while the agent session is running.
- For restricted networks, `proxychains`, `http_proxy`, and `portforward` are available.

Details: [docs/architecture.md](docs/architecture.md)

## Features

- Run agents inside a Multipass VM, not directly on the host.
- Declarative YAML for VMs, mounts, network settings, and agent defaults.
- Automatic incremental backups with hardlink snapshots.
- Several virtual machines with binding of specific agents to specific VMs, for example to separate NDA projects, work, and hobbies across different environments and models.
- Installation of supported agent CLIs into target VMs through `install-agents`.
- `proxychains` support for installation and runtime.
- VM-level and agent-level `http_proxy` support.
- Persistent SSH port forwarding through `agsekit portforward`.
- Both interactive and non-interactive CLI scenarios.
- Automatic preparation of Linux and macOS hosts.

## Documentation

- [Table of contents](docs/README.md)
  - [Getting started](docs/getting-started.md)
  - [Configuration](docs/configuration.md)
  - [Command reference](docs/commands/README.md)
  - [Supported agents](docs/agents.md)
  - [Architecture](docs/architecture.md)
  - [Networking and proxies](docs/networking.md)
  - [Backups](docs/backups.md)
  - [Troubleshooting](docs/troubleshooting.md)
  - [Practical how-to](docs/how-to.md)
  - [Known issues and limitations](docs/known-issues.md)

## Supported Agents

- [aider](https://aider.chat/)
- [Qwen Code](https://qwenlm.github.io/qwen-code-docs/en/)
- [ForgeCode](https://forgecode.dev/)
- [Codex](https://openai.com/codex/)
- [OpenCode](https://opencode.ai/)
- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- [Cline](https://cline.bot/)
- `codex-glibc` - a [Codex](https://openai.com/codex/) variant built inside the VM
- `codex-glibc-prebuilt` - a [Codex](https://openai.com/codex/) variant installed from a ready prebuilt release

Details: [docs/agents.md](docs/agents.md)

## Security Model and Limitations

What the tool does:

- isolates agent execution inside a VM;
- keeps the host project in mounted storage;
- creates rollback-friendly backups around agent runs.

More details: [philosophy.md](philosophy.md)

## Platform Support

- Linux host: supported
- macOS host: supported
- Windows host: currently only through WSL

## FAQ

### Who is this for?

For developers who want to use coding agents but do not want to break their system.

### Do I need to use git with agsekit?

Yes. `agsekit` complements git, it does not replace it.

### Why Multipass, not Docker?

1. Security: a VM gives much better isolation of the agent from your system
2. Environment reality: in a VM the agent can install any software, run Docker containers, and do almost everything that can be done on a real machine. In Docker this is impossible or much more complicated

## Contributing and License

- If you want to contribute:
  - Fork repo
  - `git clone ...`
  - `pip install -e .`
  - `git checkout -b new-shiny-feature`
  - `vim ...`
  - `git add . && git commit -m "Implemented new feature" && git push`
  - create pull request
- If there are problems, write Issues

- License: [MIT](LICENSE)
