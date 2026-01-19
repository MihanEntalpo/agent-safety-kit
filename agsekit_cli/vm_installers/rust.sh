#!/usr/bin/env bash
set -euo pipefail

if command -v rustc >/dev/null 2>&1 && command -v cargo >/dev/null 2>&1; then
  echo "Rust toolchain is already installed."
  exit 0
fi

echo "Installing Rust toolchain via rustup..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y build-essential curl

curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

ensure_line() {
  local line="$1"
  local file="$2"
  if [ ! -f "$file" ]; then
    touch "$file"
  fi
  if ! grep -Fqx "$line" "$file"; then
    echo "$line" >> "$file"
  fi
}

ensure_line "source \"$HOME/.cargo/env\"" "$HOME/.profile"
ensure_line "source \"$HOME/.cargo/env\"" "$HOME/.bashrc"
ensure_line "source \"$HOME/.cargo/env\"" "$HOME/.bash_profile"

echo "Rust installation complete."
