#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF' 1>&2
Usage:
  ./run_with_http_proxy.sh --url <http://host:port> -- <program> [args...]
  ./run_with_http_proxy.sh --upstream <scheme://host:port> [--listen <host:port|port>] --pool-start <port> --pool-end <port> -- <program> [args...]

Runs a command with HTTP_PROXY/http_proxy set. In upstream mode it starts a temporary privoxy instance inside the VM.
EOF
  exit 2
}

direct_url=""
upstream_url=""
listen_addr=""
pool_start=""
pool_end=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      shift
      [[ $# -gt 0 ]] || usage
      direct_url="$1"
      shift
      ;;
    --upstream)
      shift
      [[ $# -gt 0 ]] || usage
      upstream_url="$1"
      shift
      ;;
    --listen)
      shift
      [[ $# -gt 0 ]] || usage
      listen_addr="$1"
      shift
      ;;
    --pool-start)
      shift
      [[ $# -gt 0 ]] || usage
      pool_start="$1"
      shift
      ;;
    --pool-end)
      shift
      [[ $# -gt 0 ]] || usage
      pool_end="$1"
      shift
      ;;
    --help|-h)
      usage
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

[[ $# -gt 0 ]] || usage

if [[ -n "$direct_url" && -n "$upstream_url" ]]; then
  echo "Only one of --url or --upstream may be used." >&2
  usage
fi

if [[ -z "$direct_url" && -z "$upstream_url" ]]; then
  usage
fi

temp_dir=""
privoxy_pid=""
privoxy_config_path=""

cleanup() {
  if [[ -n "$privoxy_pid" ]] && kill -0 "$privoxy_pid" >/dev/null 2>&1; then
    kill "$privoxy_pid" >/dev/null 2>&1 || true
    wait "$privoxy_pid" >/dev/null 2>&1 || true
  fi
  if [[ -n "$privoxy_config_path" ]]; then
    sudo rm -f "$privoxy_config_path" >/dev/null 2>&1 || true
    sudo pkill -f -- "$privoxy_config_path" >/dev/null 2>&1 || true
  fi
  if [[ -n "$temp_dir" && -d "$temp_dir" ]]; then
    rm -rf "$temp_dir"
  fi
}

trap cleanup EXIT INT TERM

if [[ -n "$direct_url" ]]; then
  export HTTP_PROXY="$direct_url"
  export http_proxy="$direct_url"
  "$@"
  exit $?
fi

command -v privoxy >/dev/null 2>&1 || {
  echo "privoxy is not installed inside the VM" >&2
  exit 1
}

normalize_listen() {
  python3 - "$1" <<'PYCODE'
import sys

raw = sys.argv[1].strip()
if not raw:
    sys.stderr.write("Empty listen address\n")
    sys.exit(2)

if raw.isdigit():
    port = int(raw)
    if port <= 0 or port > 65535:
        sys.stderr.write("Invalid TCP port\n")
        sys.exit(2)
    print(f"127.0.0.1:{port}")
    sys.exit(0)

if ":" not in raw:
    sys.stderr.write("Listen address must be PORT or HOST:PORT\n")
    sys.exit(2)

host, port_text = raw.rsplit(":", 1)
if not host:
    sys.stderr.write("Listen address host is empty\n")
    sys.exit(2)
try:
    port = int(port_text)
except ValueError:
    sys.stderr.write("Listen address port must be numeric\n")
    sys.exit(2)
if port <= 0 or port > 65535:
    sys.stderr.write("Invalid TCP port\n")
    sys.exit(2)

print(f"{host}:{port}")
PYCODE
}

ensure_listen_available() {
  python3 - "$1" <<'PYCODE'
import socket
import sys

host, port_text = sys.argv[1].rsplit(":", 1)
port = int(port_text)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind((host, port))
except OSError as exc:
    sys.stderr.write(f"Listen address {host}:{port} is not available: {exc}\n")
    sys.exit(2)
finally:
    sock.close()
PYCODE
}

pick_free_listen() {
  python3 - "$1" "$2" <<'PYCODE'
import socket
import sys

start = int(sys.argv[1])
end = int(sys.argv[2])
for port in range(start, end + 1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        sock.close()
        continue
    sock.close()
    print(f"127.0.0.1:{port}")
    sys.exit(0)

sys.stderr.write(f"No free listen port found in range {start}-{end}\n")
sys.exit(2)
PYCODE
}

generate_privoxy_config() {
  python3 - "$1" "$2" "$3" "$4" <<'PYCODE'
import pathlib
import sys
from urllib.parse import urlparse

upstream_url = sys.argv[1]
listen_addr = sys.argv[2]
config_path = pathlib.Path(sys.argv[3])
log_dir = pathlib.Path(sys.argv[4])

parsed = urlparse(upstream_url)
if not parsed.scheme or not parsed.hostname or not parsed.port:
    sys.stderr.write("Upstream proxy must be scheme://host:port\n")
    sys.exit(2)

scheme = parsed.scheme.lower()
if scheme in {"http", "https"}:
    forward_line = f"forward / {parsed.hostname}:{parsed.port}"
elif scheme == "socks4":
    forward_line = f"forward-socks4a / {parsed.hostname}:{parsed.port} ."
elif scheme == "socks5":
    forward_line = f"forward-socks5 / {parsed.hostname}:{parsed.port} ."
else:
    sys.stderr.write(f"Unsupported upstream proxy scheme: {scheme}\n")
    sys.exit(2)

config = f"""confdir /etc/privoxy
templdir /etc/privoxy/templates
logdir {log_dir}
actionsfile match-all.action
actionsfile default.action
actionsfile user.action
filterfile default.filter
listen-address {listen_addr}
logfile logfile
toggle 1
enable-edit-actions 0
enable-remote-toggle 0
enable-remote-http-toggle 0
enforce-blocks 0
buffer-limit 4096
{forward_line}
"""

config_path.write_text(config, encoding="utf-8")
PYCODE
}

wait_for_port() {
  python3 - "$1" <<'PYCODE'
import socket
import sys
import time

host, port_text = sys.argv[1].rsplit(":", 1)
port = int(port_text)

deadline = time.time() + 5.0
while time.time() < deadline:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        sock.connect((host, port))
        sock.close()
        sys.exit(0)
    except OSError:
        sock.close()
        time.sleep(0.1)

sys.exit(1)
PYCODE
}

if [[ -n "$listen_addr" ]]; then
  listen_addr="$(normalize_listen "$listen_addr")"
  ensure_listen_available "$listen_addr"
else
  [[ -n "$pool_start" && -n "$pool_end" ]] || usage
  listen_addr="$(pick_free_listen "$pool_start" "$pool_end")"
fi

listen_host="${listen_addr%:*}"
listen_port="${listen_addr##*:}"
client_host="$listen_host"
if [[ "$client_host" == "0.0.0.0" ]]; then
  client_host="127.0.0.1"
fi

temp_dir="$(mktemp -d /tmp/agsekit-http-proxy-XXXXXX)"
log_dir="$temp_dir/logdir"
config_path="$temp_dir/privoxy.conf"
stdout_path="$temp_dir/privoxy.out"
privoxy_config_path="/etc/privoxy/$(basename "$temp_dir").conf"
chmod 0755 "$temp_dir"
mkdir -p "$log_dir"
chmod 0777 "$log_dir"

generate_privoxy_config "$upstream_url" "$listen_addr" "$config_path" "$log_dir"
chmod 0644 "$config_path"
sudo cp "$config_path" "$privoxy_config_path"

sudo privoxy --no-daemon "$privoxy_config_path" >"$stdout_path" 2>&1 &
privoxy_pid="$!"

if ! wait_for_port "$listen_addr"; then
  if [[ -f "$stdout_path" ]]; then
    cat "$stdout_path" >&2 || true
  fi
  echo "privoxy failed to start on $listen_addr" >&2
  exit 1
fi

export HTTP_PROXY="http://$client_host:$listen_port"
export http_proxy="http://$client_host:$listen_port"

"$@"
exit $?
