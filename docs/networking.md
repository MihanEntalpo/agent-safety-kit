# Networking and Proxies

`agsekit` supports three main networking helpers:

- `proxychains`
- `http_proxy`
- SSH `portforward`

## proxychains

Use `proxychains` when the agent or installer must run through a SOCKS or proxy-aware wrapper.

You can configure it:

- per VM in config;
- per command with `--proxychains scheme://host:port`;
- disabled for one run with `--proxychains ""`.

## http_proxy

`http_proxy` can be resolved from the VM or agent configuration.

### Direct Mode

Provide a ready-to-use HTTP proxy URL and `agsekit` injects `HTTP_PROXY` and `http_proxy` into the agent environment.

### Upstream Mode

Provide an upstream proxy URL and `agsekit` starts a temporary `privoxy` inside the VM for that run. The local listening port is chosen from `global.http_proxy_port_pool` when not explicitly set.

## Mutual Exclusion

For one `run`, effective `http_proxy` and effective `proxychains` are mutually exclusive. `agsekit` fails fast instead of guessing which transport should win.

## Port Forwarding

`agsekit portforward` maintains SSH tunnels for configured VMs and re-reads the config periodically to reconnect when rules change.

## Typical Use Cases

- corporate SOCKS proxy for model access
- direct HTTP proxy for OpenAI-compatible API access
- stable local tunnel for accessing guest services on the host

## See Also

- [Networking commands](commands/networking.md)
- [run](commands/run.md)
- [Configuration](configuration.md)
