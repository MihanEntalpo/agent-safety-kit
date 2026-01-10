#!/usr/bin/env bash
set -euo pipefail

PROXYCHAINS_PROXY="${AGSEKIT_PROXYCHAINS_PROXY:-}"
PROXYCHAINS_CONFIG=""

init_proxychains() {
  if [ -z "$PROXYCHAINS_PROXY" ]; then
    return 1
  fi

  if [ -n "$PROXYCHAINS_CONFIG" ]; then
    return 0
  fi

  if ! command -v proxychains4 >/dev/null 2>&1; then
    echo "proxychains4 not found, installing via apt-get..." >&2
    if command -v sudo >/dev/null 2>&1; then
      sudo apt-get update -y
      sudo apt-get install -y proxychains4
    else
      apt-get update -y
      apt-get install -y proxychains4
    fi
  fi

  PROXYCHAINS_CONFIG="$(mktemp /tmp/agsekit-proxychains-XXXX.conf)"
  trap 'rm -f "$PROXYCHAINS_CONFIG"' EXIT INT TERM

  python3 - "$PROXYCHAINS_PROXY" "$PROXYCHAINS_CONFIG" <<'PYCODE'
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
# proxychains-ng localnet accepts CIDR/mask plus domain globs like *.local.
localnet 127.0.0.0/255.0.0.0
localnet *.local

[ProxyList]
{proxy_type} {parsed.hostname} {parsed.port}
"""

config_path.write_text(config, encoding="utf-8")
PYCODE
}

run_with_proxychains() {
  if [ -z "$PROXYCHAINS_PROXY" ]; then
    "$@"
    return
  fi

  init_proxychains
  proxychains4 -f "$PROXYCHAINS_CONFIG" "$@"
}

echo "Installing Claude Code agent..."

run_with_proxychains curl -fsSL https://claude.ai/install.sh | bash
