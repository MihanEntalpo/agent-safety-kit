# How-To Recipes

This page collects short practical recipes that are useful early in adoption.

## Use an OpenAI-Compatible API

The exact flags depend on the agent CLI, but the pattern is always the same:

1. configure provider-specific defaults in the agent profile or pass them at runtime;
2. keep secrets outside the repository;
3. use the same agent flags you would use without `agsekit`.

Related reading:

- [Supported agents](agents.md)
- [run](commands/run.md)

## Work Behind a Restricted Network

Use one of these approaches:

- `proxychains` when the runtime should be wrapped by a proxy-aware command layer;
- `http_proxy` direct mode when you already have an HTTP proxy;
- `http_proxy` upstream mode when `agsekit` should spin up temporary `privoxy` inside the VM.

Do not use effective `proxychains` and effective `http_proxy` together for the same `run`.

## Use `proxychains`

Typical flow:

```bash
agsekit install-agents qwen --proxychains socks5://127.0.0.1:1080
cd /path/to/project
agsekit run --proxychains socks5://127.0.0.1:1080 qwen
```

## Use `http_proxy`

Direct mode example:

```yaml
vms:
  agent-ubuntu:
    http_proxy:
      url: http://127.0.0.1:18881
```

Upstream mode example:

```yaml
vms:
  agent-ubuntu:
    http_proxy: socks5://127.0.0.1:8181
```

## Use `portforward`

Define forwarding rules in config and keep them alive with:

```bash
agsekit portforward
```

On Linux, the same behavior can be kept in the background through the `systemd` integration.

## See Also

- [Networking](networking.md)
- [Networking commands](commands/networking.md)
- [systemd](commands/systemd.md)
