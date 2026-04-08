# Supported Agents

`agsekit` manages installation and runtime launching for a fixed set of agent types.

## Supported Types

- `aider`
- `qwen`
- `forgecode`
- `codex`
- `opencode`
- `claude`
- `cline`
- `codex-glibc`
- `codex-glibc-prebuilt`

## Installation Model

The `install-agents` command chooses the Ansible playbook for the selected type and installs the matching runtime into the target VM.

Common patterns:

- npm CLI installs for `codex`, `qwen`, `opencode`, and `cline`
- official installer flows for `aider`, `forgecode`, and `claude`
- local source build for `codex-glibc`
- release asset download for `codex-glibc-prebuilt`

## Runtime Model

`agsekit run` resolves the selected agent profile, applies default arguments, mount restrictions, VM restrictions, and networking settings, then starts the agent inside the VM.

## OpenAI-Compatible APIs

The exact runtime flags depend on the agent CLI. The usual pattern is:

1. add provider-specific default arguments in the `agents.<name>.default-args` section or pass them at runtime;
2. keep secrets outside the repo;
3. use the same provider-specific flags you would use without `agsekit`.

## Notes

- `forgecode` runtime forces `FORGE_TRACKER=false`.
- `codex-glibc` and `codex-glibc-prebuilt` are separate binaries and can coexist with `codex`.
- `codex-glibc-prebuilt` can be redirected to another GitHub release source through host environment variables.

## See Also

- [install-agents](commands/install-agents.md)
- [run](commands/run.md)
- [Networking](networking.md)
