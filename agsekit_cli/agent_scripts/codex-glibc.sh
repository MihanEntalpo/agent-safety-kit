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

echo "Building Codex agent with glibc toolchain..."

sudo apt-get update -y
sudo apt-get install -y build-essential pkg-config libssl-dev curl git

if ! command -v rustup >/dev/null 2>&1; then
  echo "Installing Rust toolchain via rustup..."
  RUSTUP_INSTALLER="$(mktemp -t rustup-init-XXXXXX.sh)"
  echo "Downloading rustup installer to $RUSTUP_INSTALLER ..."
  run_with_proxychains curl --proto '=https' --tlsv1.2 -fL https://sh.rustup.rs -o "$RUSTUP_INSTALLER"
  echo "Running rustup installer in batch mode (-y)..."
  export RUSTUP_INIT_SKIP_PATH_CHECK=yes
  ( set -x; sh "$RUSTUP_INSTALLER" -y --no-modify-path )
  rm -f "$RUSTUP_INSTALLER"
  echo "Rustup installation finished."
fi

if [ -f "$HOME/.cargo/env" ]; then
  # shellcheck disable=SC1090
  . "$HOME/.cargo/env"
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "Cargo is unavailable after rustup installation. Please check your Rust setup."
  exit 1
fi

HOST_TARGET="$(rustc -Vv | awk '/host:/ {print $2}')"
if [ -z "$HOST_TARGET" ]; then
  ARCH="$(uname -m)"
  HOST_TARGET="${ARCH}-unknown-linux-gnu"
fi

run_with_proxychains rustup target add "$HOST_TARGET"

BUILD_ROOT="$(mktemp -d -t codex-src-XXXXXX)"
trap 'rm -rf "$BUILD_ROOT"' EXIT

echo "Cloning codex repository..."
run_with_proxychains git clone --depth 1 https://github.com/openai/codex.git "$BUILD_ROOT/codex"

echo "Compiling codex for target ${HOST_TARGET}..."
(
  cd "$BUILD_ROOT/codex"
  run_with_proxychains cargo build --release --target "$HOST_TARGET"
)

BUILT_BINARY="$BUILD_ROOT/codex/target/$HOST_TARGET/release/codex"
if [ ! -x "$BUILT_BINARY" ]; then
  echo "Expected binary not found at $BUILT_BINARY"
  exit 1
fi

DEST_PATH="/usr/local/bin/codex-glibc"
if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  sudo install -m 0755 "$BUILT_BINARY" "$DEST_PATH"
  echo "Installed codex-glibc to $DEST_PATH using sudo."
else
  mkdir -p "$HOME/.local/bin"
  install -m 0755 "$BUILT_BINARY" "$HOME/.local/bin/codex-glibc"
  DEST_PATH="$HOME/.local/bin/codex-glibc"
  if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.profile" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
    echo "Added $HOME/.local/bin to PATH in ~/.profile."
  fi
  echo "Installed codex-glibc to $DEST_PATH."
fi
