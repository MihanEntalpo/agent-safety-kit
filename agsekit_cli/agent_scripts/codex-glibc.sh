#!/usr/bin/env bash
set -euo pipefail

echo "Building Codex agent with glibc toolchain..."

sudo apt-get update -y
sudo apt-get install -y build-essential pkg-config libssl-dev curl git

if ! command -v rustup >/dev/null 2>&1; then
  echo "Installing Rust toolchain via rustup..."
  RUSTUP_INSTALLER="$(mktemp -t rustup-init-XXXXXX.sh)"
  echo "Downloading rustup installer to $RUSTUP_INSTALLER ..."
  curl --proto '=https' --tlsv1.2 -fL https://sh.rustup.rs -o "$RUSTUP_INSTALLER"
  echo "Running rustup installer in batch mode (-y)..."
  ( set -x; sh "$RUSTUP_INSTALLER" -y )
  rm -f "$RUSTUP_INSTALLER"
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

rustup target add "$HOST_TARGET"

BUILD_ROOT="$(mktemp -d -t codex-src-XXXXXX)"
trap 'rm -rf "$BUILD_ROOT"' EXIT

echo "Cloning codex repository..."
git clone --depth 1 https://github.com/openai/codex.git "$BUILD_ROOT/codex"

echo "Compiling codex for target ${HOST_TARGET}..."
(
  cd "$BUILD_ROOT/codex"
  cargo build --release --target "$HOST_TARGET"
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
