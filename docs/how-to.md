# Practical How-To

This page collects short practical recipes that are useful in the early stage of use.

## Contents

- [Mounting Folders](#mounting-folders)
- [Self-Hosted OpenAI-Compatible API](#self-hosted-openai-compatible-api)
- [Running codex and claude-code with Access Restrictions](#running-codex-and-claude-code-with-access-restrictions)

## Mounting Folders

* Do not use folders whose names contain non-ASCII characters; this is a Multipass limitation.

## Self-Hosted OpenAI-Compatible API

If you have your own self-hosted LLM with an OpenAI API, configuring it in different agents is sometimes not very trivial.

Here are instructions for some of the supported agents (the list is updated).

Assume you have the following data (for example):

```
OPENAI_BASE_URL=http://127.0.0.1:8080/v1 - address of your vLLM inference server
OPENAI_API_KEY="my-very-secure-key"
OPENAI_MODEL="Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
```

### Qwen

Parameters can be passed through env variables.

1. Change the agsekit configuration by setting env variables:

```yaml
...
agents:
...
  qwen:
    type: qwen
    env:
      OPENAI_API_KEY: "my-very-secure-key"
      OPENAI_BASE_URL: "http://127.0.0.1:8080/v1"
      OPENAI_MODEL: "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
...
```

2. After that, run qwen, and it will ask which API to use: cloud or local. Select local, and the connection data will be filled in from env.

```shell
agsekit run qwen
```

### Cline

Parameters can be passed with a special command.

1. Suppose you have an agsekit configuration with a cline agent:

```yaml
...
agents:
...
  cline:
    type: cline
```

2. Run the command:

```shell
agsekit run cline auth -p openai -k "my-very-secure-key" -m "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8" -b "http://127.0.0.1:8080/v1"
```

After that, run:

```shell
agsekit run cline
```

and the setup will already be done.

### ForgeCode

1. Set env variables in the agsekit config:

```yaml
...
agents:
...
  forgecode:
    type: forgecode
    env:
      OPENAI_API_KEY: "my-very-secure-key"
      OPENAI_URL: "http://127.0.0.1:8080/v1"
```

2. Run the agent:

```shell
agsekit run forgecode
```

3. On first launch, the provider selection window will open.

Select OpenAI Compatible.

All other data will be pulled from env variables, and the model variant (if you have several of them) can be selected with a separate command.

### Aider

1. Configure env variables and arguments in the agsekit config:

```yaml
...
agents:
...
  aider:
    type: aider
    proxychains: ""
    env:
      OPENAI_API_KEY: "my-very-secure-key"
      OPENAI_API_BASE: "http://127.0.0.1:8080/v1"
    default-args:
      - "--model"
      - "openai/Qwen/Qwen3-Coder-30B-A3B-Instruct"
      - "--no-gitignore"

```

Note that before the name of your model in `--model`, you need to add the "openai/" prefix. It is responsible for determining the "provider type".

2. Run the agent:

```shell
agsekit run aider
```

### Other Agents

... In development ...

- [Supported agents](agents.md)
- [run](commands/run.md)

## Running codex and claude-code with Access Restrictions

Suppose you do not have access to the OpenAI and Anthropic APIs, which prevents you from using codex/claude-code.

At the same time, suppose you have SSH access to some server on the internet/at home, from which access to those APIs is not restricted.

What can you do?

1. Configure a permanent socks-proxy

If you use Linux/macOS, you can use autossh to configure permanent forwarding of a socks5-proxy port.

Write a script like this:

```shell
#!/bin/bash

# your host for ssh connection
SSH_USER_HOST="user@remove-vps-host.com"
# Path to private key for ssh
PRIV_KEY="/home/user/.ssh/id_rsa"
# Port on which the socks-proxy will listen
LISTEN="127.0.01:8087"

killall autossh

nohup autossh -M 10984 -N -o "PubkeyAuthentication=yes" -o "PasswordAuthentication=no" -i /"$PRIV_KEY" -o "BatchMode=yes" -o "ConnectTimeout=10" \
    $SSH_USER_HOST -D $LISTEN &
```

Put it in `~/autossh.sh`, make it executable, and add it to system autostart in any convenient way.

2. Configure port forwarding and proxychains

In the agsekit configuration:

```shell
vms:
  agents-ubuntu:
    ...
    port-forwarding:
      - type: remote
        # The connection will be forwarded to this host port
        host-addr: 127.0.0.1:8087
        # when connecting to this VM port
        vm-addr: 127.0.0.1:8087

agents:
  codex:
    type: codex-glibc-prebuilt # use this type because it supports proxychains
    # Configure proxychains to the port that leads to the host socks5-proxy
    proxychains: socks5://127.0.0.1:8087

  claude:
    type: claude
    # Configure http-proxy to launch temporary proxify on a random port and forward traffic to the host socks5-proxy
    http_proxy: socks5://127.0.0.1:8087
```

On Linux you can configure the systemd daemon with `agsekit systemd install`, and port forwarding will be maintained automatically.

On Windows / macOS you can run `agsekit portforward` in a separate terminal, and port forwarding will be maintained while that terminal is alive.

## See Also

- [Networking and proxies](networking.md)
- [Networking commands](commands/networking.md)
- [systemd](commands/systemd.md)
