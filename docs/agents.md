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

Agent versions are not pinned by default. Set `agents.<name>.version` to `stable` to use agsekit's known-good tested version, or set an exact semver version when reproducibility is required.

Each agent type also knows how to query its latest installable upstream version. The daily version check runs only for the unique agent types present in the config and caches the result with its refresh timestamp in `state.yaml`. It does not inspect VMs. `install-agents --upgrade` uses this cache to upgrade selected agents without registry lookups during installation.

Main patterns:

- latest or exact npm CLI versions for `codex`, `qwen`, `opencode`, `claude`, and `cline`
- exact Python package version for `aider`
- exact release version for `forgecode`
- local build from source for `codex-glibc`
- exact release asset download for `codex-glibc-prebuilt`

## Runtime Model

`agsekit run` resolves the agent profile, applies default arguments, env, mount/VM restrictions, and network settings, then launches the agent inside the VM.

## OpenAI-Compatible API and Other Settings

Specific runtime flags depend on the agent CLI. The usual pattern is:

1. add provider-specific default arguments to `agents.<name>.default-args`, `agents.<name>.env`, or pass them at runtime;
2. do not store secrets in the repository;
3. use the same provider-specific flags as without `agsekit`.

Unfortunately, every agent is configured in its own way, so you need to look in their documentation for how to connect a specific agent to a specific network.

## Notes

- some agents receive built-in default environment variables at runtime before `agents.<name>.env` from the config is applied; user config can still override them if needed
- current built-in defaults are: `forgecode -> FORGE_TRACKER=false`, `aider -> AIDER_CHECK_UPDATE=false`, `opencode -> OPENCODE_DISABLE_AUTOUPDATE=true`, `claude -> DISABLE_AUTOUPDATER=1`, `cline -> CLINE_NO_AUTO_UPDATE=1`
- `codex-glibc` and `codex-glibc-prebuilt` are separate binaries and can coexist with `codex`.
- the release source for `codex-glibc-prebuilt` can be overridden through host environment variables.
- when `install-agents` sees an already installed binary with a different version, it reinstalls that agent to reach the requested version from the config.
- `install-agents --upgrade` temporarily uses the cached latest version instead of the configured pin and does not rewrite the config.
- adding `--force-check-versions` to `--upgrade` refreshes selected types from upstream immediately and refuses stale-cache fallback when a refresh fails.

## See Also

- [install-agents](commands/install-agents.md)
- [run](commands/run.md)
- [Networking](networking.md)
