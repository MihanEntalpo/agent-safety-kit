#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF' 1>&2
Usage: ./run_with_proxychains.sh --proxy <scheme://host:port> <program> [args...]

Creates a temporary proxychains4 config for the provided proxy and executes the program through proxychains4.
EOF
  exit 2
}

proxy_setting=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --proxy)
      shift
      [[ $# -gt 0 ]] || usage
      proxy_setting="$1"
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

[[ -n "$proxy_setting" ]] || usage
[[ $# -gt 0 ]] || usage

if ! command -v proxychains4 >/dev/null 2>&1; then
  echo "proxychains4 не найден, устанавливаю через sudo apt-get..." >&2
  sudo apt-get update
  sudo apt-get install -y proxychains4
fi

config_file="$(mktemp /tmp/agsekit-proxychains-XXXX.conf)"

cleanup() {
  rm -f "$config_file"
}
trap cleanup EXIT INT TERM

python3 - "$proxy_setting" "$config_file" <<'PYCODE'
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

exec proxychains4 -q -f "$config_file" "$@"
