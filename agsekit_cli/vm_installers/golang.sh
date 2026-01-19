#!/usr/bin/env bash
set -euo pipefail

if command -v go >/dev/null 2>&1; then
  echo "Go toolchain is already installed."
  exit 0
fi

echo "Installing Go toolchain..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y golang-go build-essential

echo "Go installation complete."
