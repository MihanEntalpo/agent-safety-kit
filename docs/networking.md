# Networking and Proxies

`agsekit` supports three main network helpers:

- `proxychains` - the ability to run agents wrapped in proxychains4
- `http_proxy` - the ability to run agents with a preliminary HTTP proxy launch and HTTP_PROXY environment variables set
- `portforward` - port forwarding into and out of the VM through SSH tunnels

## Contents

- [Proxychains](#proxychains)
- [HTTP_PROXY](#http_proxy)
- [Port Forwarding](#port-forwarding)
- [Typical Scenarios](#typical-scenarios)

## Proxychains

If you have a restricted network and a socks5/http/https proxy server that allows connecting to the agent, you can call both the agent installer and the agent itself through proxychains4.

For detailed information about "what proxychains is", see its documentation: https://github.com/haad/proxychains.

In short, it is a way to force an application to send all its traffic through a proxy server, even if the application does not support working with a proxy.

It can be set:

- at the VM level in config: `vms.<vm_name>.proxychains: scheme://host:port`;
- at the agent level in its config: `agents.<agent_name>.proxychains: scheme://host:port`
- at the command level through `--proxychains scheme://host:port`;
- disabled for one run through `--proxychains ""`

**Example:**

1. Access to the Qwen neural network or the NPM repository from which the qwen agent is installed is blocked for you.
2. However, you can connect over SSH to some PC/server that has such access.
3. On your host system, you can connect to that remote server over SSH with argument `-D 127.0.0.1:8080`, and now you have a socks5 proxy on that port.
4. Next, you can forward that port into the VM using portforward (more on this later).
5. And enable `vms.<vm_name>.proxychains: socks5://127.0.0.1:8080` in the VM settings, or in agent settings: `agents.<agent_name>.proxychains: socks5://127.0.0.1:8080`

## HTTP_PROXY

If your agent does not support working through proxychains, but can work through HTTP_PROXY and respects the corresponding env variable, you can use http_proxy.

Such an agent is, for example, Claude-code.

It can be set:

- at the VM level in config: `vms.<vm_name>.http_proxy: scheme://host:port`;
- at the agent level in its config: `agents.<agent_name>.http_proxy: scheme://host:port`
- at the command level through `--http-proxy scheme://host:port`;
- disabled for one run through `--http-proxy ""`

There are different ways to set http_proxy:

### Direct Mode

If there is already an open port inside the VM where a ready HTTP proxy is available, and you only need to pass this information in the HTTP_PROXY env variable, the configuration can be written like this:

```shell
# Can be set for a VM
vms:
  agent-ubuntu:
    ...
    http_proxy:
      # url is the address of the already existing http-proxy
      url: http://127.0.0.1:8080

# Can be set for an agent
agents:
  qwen:
    type: qwen
    http_proxy:
      # url is the address of the already existing http-proxy
      url: http://127.0.0.1:8080
```

You pass a ready HTTP proxy URL, and `agsekit` simply sets `HTTP_PROXY` and `http_proxy` in the agent environment.

### Upstream Mode

If you have a socks5/socks4 proxy that cannot be used directly as an http-proxy, you can specify it, and in this case a temporary `privoxy` http-proxy will be started.

Full form:

```shell
# Can be set for a VM
vms:
  agent-ubuntu:
    ...
    http_proxy:
      # socks-proxy on this port
      upstream: socks5://127.0.0.1:5000
      # Listen for http-proxy on this port
      listen: 127.0.0.1:8080

# Can be set for an agent
agents:
  qwen:
    type: qwen
    http_proxy:
      # url is the address of the already existing http-proxy
      upstream: socks5://127.0.0.1:5000
      # listen for http-proxy on this port
      listen: 127.0.0.1:8080
```

If listen is not specified, a random free port from `global.http_proxy_port_pool` will be selected for it.

If only a port is specified in listen, for example 8080, it is equivalent to "127.0.0.1:8080".

Short form:

By default, an entry like `http_proxy: socks5://127.0.0.1:5000` is a short form of:

```yaml
...
    http_proxy:
      upstream: socks5://127.0.0.1:5000
...
```

The `--http-proxy` flag uses exactly this upstream mode.

## Mutual Exclusion

One `run` cannot have both `http_proxy` and `proxychains` at the same time. `agsekit` exits with an error instead of trying to guess which transport matters more.

## Port Forwarding

The `agsekit portforward` command, as well as the daemon started through `agsekit systemd start`, creates and maintains SSH tunnels into and out of the VM and periodically rereads the config to reconnect forwards when rules change.

If you do not know what SSH tunnels are, you can read about them here: https://docs.oracle.com/en/operating-systems/oracle-linux/openssh/openssh-SettingUpPortForwardingOverSSH.html

In short, they allow opening a port inside the VM that lets you connect to a service from outside, as well as opening ports outside that allow connecting to a service inside.

Example configuration:

```shell
vms:
  agents-ubuntu:
    ...
    port-forwarding:
      # Types are: remote, local, socks
      # remote means connection from inside the VM to the host
      - type: remote
        host-addr: 127.0.0.1:5432 # Forward host PostgreSQL
        vm-addr: 127.0.0.1:5432
      # local means connection from the host into the VM
      - type: local
        host-addr: 127.0.0.1:8080 # Connect from outside to nginx running inside the VM
        vm-addr: 127.0.0.1:80
      # socks5 - open a socks5 proxy port inside the VM leading to the host
      - type: socks5
        # Useful for complex routing, when for some reason the VM cannot get access
        # to an address that the main OS connects to perfectly fine
        vm-addr: 127.0.0.1:11800
```

The configuration can be changed while running, and portforward will automatically update the tunnels, closing unneeded ones and raising new needed ones.

## Typical Scenarios

- You have a corporate SOCKS proxy for model access
- There is a web server inside the VM, for example nginx, and you want to view its output in the main VM
- You want to give the VM access to your local PostgreSQL DB at 127.0.0.1 so you do not have to fiddle with pg_hba.conf
