# Troubleshooting

This page collects the most common operational failures.

## `multipass` commands hang or fail

Check:

- whether stale test VMs are still running;
- whether the Multipass daemon itself is healthy;
- whether mounted folders are still visible inside the guest.

`agsekit doctor` can detect at least one known stale-mount case.

## Ansible playbook fails in progress mode

Recent `agsekit` versions buffer hidden Ansible output and print the last lines when a playbook fails. Re-run with `--debug` if you need the full play output.

## A mount looks empty inside the VM

This can be a Multipass mount issue rather than a config issue. Check:

- `agsekit status`
- `multipass info <vm>`
- `agsekit doctor`

## Agent run fails on networking

Verify:

- `proxychains` and `http_proxy` are not both effective for the same run;
- the upstream proxy is reachable;
- SSH port forwards are not conflicting locally.

## macOS host notes

- Multipass installation goes through Homebrew.
- Linux-only `systemd` integration is skipped.

## See Also

- [Known issues](known-issues.md)
- [doctor](commands/doctor.md)
- [Networking](networking.md)
