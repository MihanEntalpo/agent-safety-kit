#!/usr/bin/env bash

set -euo pipefail

PROXYCHAINS_PROXY="${PROXYCHAINS_PROXY:-${AGSEKIT_PROXYCHAINS_PROXY:-}}"
PROXYCHAINS_CONFIG="${PROXYCHAINS_CONFIG:-}"
PROXYCHAINS_QUIET="${PROXYCHAINS_QUIET:-0}"

_proxychains_append_trap() {
  local new_trap="$1"
  local signal="$2"
  local existing

  existing="$(trap -p "$signal" | awk -F"'" '{print $2}')"
  if [ -n "$existing" ]; then
    trap "$existing; $new_trap" "$signal"
  else
    trap "$new_trap" "$signal"
  fi
}

ensure_proxychains_installed() {
  if command -v proxychains4 >/dev/null 2>&1; then
    return 0
  fi

  echo "proxychains4 not found, installing via apt-get..." >&2
  if command -v sudo >/dev/null 2>&1 && [ "$(id -u)" -ne 0 ]; then
    sudo apt-get update -y
    sudo apt-get install -y proxychains4
  else
    apt-get update -y
    apt-get install -y proxychains4
  fi
}

build_proxychains_config() {
  local proxy_url="$1"
  local config_path="${2:-}"

  if [ -z "$config_path" ]; then
    config_path="$(mktemp /tmp/agsekit-proxychains-XXXX.conf)"
  fi

  python3 - "$proxy_url" "$config_path" <<'PYCODE'
import pathlib
import sys
from urllib.parse import urlparse

proxy_url = sys.argv[1]
config_path = pathlib.Path(sys.argv[2])

parsed = urlparse(proxy_url)
if not parsed.scheme or not parsed.hostname or not parsed.port:
    sys.stderr.write("proxychains proxy must be in the form scheme://host:port\n")
    sys.exit(2)

scheme = parsed.scheme.lower()
allowed = {"socks5", "socks4", "http", "https"}
if scheme not in allowed:
    sys.stderr.write(f"Unsupported proxy scheme for proxychains: {scheme}\n")
    sys.exit(2)

proxy_type = "http" if scheme in {"http", "https"} else scheme

config = f"""strict_chain
proxy_dns
remote_dns_subnet 224
tcp_read_time_out 15000
tcp_connect_time_out 8000
# proxychains-ng localnet accepts CIDR/mask ranges.
localnet 127.0.0.0/255.0.0.0

[ProxyList]
{proxy_type} {parsed.hostname} {parsed.port}
"""

config_path.write_text(config, encoding="utf-8")
PYCODE

  echo "$config_path"
}

run_with_proxychains() {
  if [ -z "${PROXYCHAINS_PROXY:-}" ]; then
    "$@"
    return
  fi

  ensure_proxychains_installed

  if [ -z "${PROXYCHAINS_CONFIG:-}" ]; then
    PROXYCHAINS_CONFIG="$(build_proxychains_config "$PROXYCHAINS_PROXY")"
    _proxychains_append_trap 'rm -f "$PROXYCHAINS_CONFIG"' EXIT
    _proxychains_append_trap 'rm -f "$PROXYCHAINS_CONFIG"' INT
    _proxychains_append_trap 'rm -f "$PROXYCHAINS_CONFIG"' TERM
  fi

  local proxychains_args=("-f" "$PROXYCHAINS_CONFIG")
  if [ "$PROXYCHAINS_QUIET" -eq 1 ]; then
    proxychains_args=("-q" "${proxychains_args[@]}")
  fi

  proxychains4 "${proxychains_args[@]}" "$@"
}
