#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-lts}"
NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  echo "nvm is not installed. Install the nvm bundle first." >&2
  exit 1
fi

# shellcheck disable=SC1090
. "$NVM_DIR/nvm.sh"

if [ "$VERSION" = "lts" ]; then
  if command -v node >/dev/null 2>&1; then
    echo "Node.js is already installed, keeping the current version."
    exit 0
  fi

  echo "Installing current LTS Node.js via nvm..."
  RESOLVED_VERSION="$(nvm version-remote --lts | tail -n 1)"
  if [ -z "$RESOLVED_VERSION" ] || [ "$RESOLVED_VERSION" = "N/A" ]; then
    echo "Failed to resolve the current LTS Node.js release from nvm version-remote --lts." >&2
    exit 1
  fi
  nvm install "$RESOLVED_VERSION"
  nvm alias default "$RESOLVED_VERSION"
else
  echo "Installing Node.js $VERSION via nvm..."
  nvm install "$VERSION"
  nvm alias default "$VERSION"
fi

echo "Node.js installation complete."
