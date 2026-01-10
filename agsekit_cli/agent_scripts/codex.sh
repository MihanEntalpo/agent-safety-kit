#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/proxychains_common.sh"

PROXYCHAINS_PROXY="${AGSEKIT_PROXYCHAINS_PROXY:-}"

echo "Installing Codex agent..."

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

echo "Installing Codex CLI globally..."
run_with_proxychains npm install -g @openai/codex@latest

CODEX_PREFIX="$(npm prefix -g 2>/dev/null || true)"
if [ -z "$CODEX_PREFIX" ]; then
  echo "Failed to detect the global npm prefix. Please verify your npm installation."
  exit 1
fi

CODEX_BIN_DIR="$CODEX_PREFIX/bin"
CODEX_PATH="$CODEX_BIN_DIR/codex"

if ! command -v codex >/dev/null 2>&1 && [ -x "$CODEX_PATH" ]; then
  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo ln -sf "$CODEX_PATH" /usr/local/bin/codex
    echo "Linked codex binary to /usr/local/bin/codex using sudo."
  elif [ -w /usr/local/bin ]; then
    ln -sf "$CODEX_PATH" /usr/local/bin/codex
    echo "Linked codex binary to /usr/local/bin/codex."
  else
    mkdir -p "$HOME/.local/bin"
    ln -sf "$CODEX_PATH" "$HOME/.local/bin/codex"
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.profile" 2>/dev/null; then
      echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
      echo "Added $HOME/.local/bin to PATH in ~/.profile."
    fi
    echo "Linked codex binary to $HOME/.local/bin/codex."
  fi
fi
