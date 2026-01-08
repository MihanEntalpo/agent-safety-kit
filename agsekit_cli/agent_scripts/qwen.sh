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

echo "Installing Qwen Code agent..."

NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

load_nvm() {
  if [ -s "$NVM_DIR/nvm.sh" ]; then
    # shellcheck disable=SC1090
    . "$NVM_DIR/nvm.sh"
    return 0
  fi

  if [ -s "$NVM_DIR/bash_completion" ]; then
    # shellcheck disable=SC1090
    . "$NVM_DIR/bash_completion"
    return 0
  fi

  return 1
}

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js not found, installing Node.js via nvm..."
  if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    run_with_proxychains curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
  fi

  if ! load_nvm; then
    echo "nvm installation failed: $NVM_DIR/nvm.sh is missing."
    exit 1
  fi

  run_with_proxychains bash -lc "source \"$NVM_DIR/nvm.sh\"; nvm install 24"
  load_nvm >/dev/null 2>&1 || true
  nvm use 24 >/dev/null 2>&1 || true
  echo "Node.js version after installation: $(node -v)"
  echo "npm version after installation: $(npm -v)"
else
  load_nvm >/dev/null 2>&1 || true
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is unavailable. Please install Node.js (e.g., via nvm) and retry."
  exit 1
fi

echo "Installing qwen-code CLI globally..."
run_with_proxychains npm install -g @qwen-code/qwen-code@latest

QWEN_PREFIX="$(npm prefix -g 2>/dev/null || true)"
if [ -z "$QWEN_PREFIX" ]; then
  echo "Failed to detect the global npm prefix. Please verify your npm installation."
  exit 1
fi

QWEN_BIN_DIR="$QWEN_PREFIX/bin"
QWEN_PATH="$QWEN_BIN_DIR/qwen"

if ! command -v qwen >/dev/null 2>&1 && [ -x "$QWEN_PATH" ]; then
  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo ln -sf "$QWEN_PATH" /usr/local/bin/qwen
    echo "Linked qwen binary to /usr/local/bin/qwen using sudo."
  elif [ -w /usr/local/bin ]; then
    ln -sf "$QWEN_PATH" /usr/local/bin/qwen
    echo "Linked qwen binary to /usr/local/bin/qwen."
  else
    mkdir -p "$HOME/.local/bin"
    ln -sf "$QWEN_PATH" "$HOME/.local/bin/qwen"
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.profile" 2>/dev/null; then
      echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
      echo "Added $HOME/.local/bin to PATH in ~/.profile."
    fi
    echo "Linked qwen binary to $HOME/.local/bin/qwen."
  fi
fi
