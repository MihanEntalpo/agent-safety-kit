# Supported Agents

`agsekit` manages installation and runtime launch for a fixed set of agent types.

Agents are essentially binaries from various vendors, such as claude-code, codex, or cline.

## Contents

- [Supported Types](#supported-types)
- [Installation Model](#installation-model)
- [Runtime Model](#runtime-model)
- [OpenAI-Compatible API and Other Settings](#openai-compatible-api-and-other-settings)
- [Notes](#notes)

## Supported Types

- `aider` - [aider](https://aider.chat/)
- `qwen` - [Qwen Code](https://qwenlm.github.io/qwen-code-docs/en/)
- `forgecode` - [ForgeCode](https://forgecode.dev/)
- `codex` - [Codex](https://openai.com/codex/)
- `opencode` - [OpenCode](https://opencode.ai/)
- `claude` - [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- `cline` - [Cline](https://cline.bot/)
- `codex-glibc` - a [Codex](https://openai.com/codex/) variant built inside the VM
- `codex-glibc-prebuilt` - a [Codex](https://openai.com/codex/) variant installed from a ready prebuilt release

## Installation Model

The `install-agents` command selects the Ansible playbook for the required type and installs the corresponding runtime into the target VM.

Main patterns:

- npm CLI for `codex`, `qwen`, `opencode`, and `cline`
- official installers for `aider`, `forgecode`, and `claude`
- local build from source for `codex-glibc`
- release asset download for `codex-glibc-prebuilt`

## Runtime Model

`agsekit run` resolves the agent profile, applies default arguments, env, mount/VM restrictions, and network settings, then launches the agent inside the VM.

## OpenAI-Compatible API and Other Settings

Specific runtime flags depend on the agent CLI. The usual pattern is:

1. add provider-specific default arguments to `agents.<name>.default-args`, `agents.<name>.env`, or pass them at runtime;
2. do not store secrets in the repository;
3. use the same provider-specific flags as without `agsekit`.

Unfortunately, every agent is configured in its own way, so you need to look in their documentation for how to connect a specific agent to a specific network.

## Notes

- runtime `forgecode` always receives `FORGE_TRACKER=false`, because otherwise forgecode sends your data "for statistics", including email and name from `.gitconfig`
- `codex-glibc` and `codex-glibc-prebuilt` are separate binaries and can coexist with `codex`.
- the release source for `codex-glibc-prebuilt` can be overridden through host environment variables.

## See Also

- [install-agents](commands/install-agents.md)
- [run](commands/run.md)
- [Networking](networking.md)
