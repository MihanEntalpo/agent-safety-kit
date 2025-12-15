#!/usr/bin/env bash
set -euo pipefail

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
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
  fi

  if ! load_nvm; then
    echo "nvm installation failed: $NVM_DIR/nvm.sh is missing."
    exit 1
  fi

  nvm install 24
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
npm install -g @qwen-code/qwen-code@latest
