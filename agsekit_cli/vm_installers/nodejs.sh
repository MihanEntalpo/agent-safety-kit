#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-latest}"
NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  echo "nvm is not installed. Install the nvm bundle first." >&2
  exit 1
fi

# shellcheck disable=SC1090
. "$NVM_DIR/nvm.sh"

if [ "$VERSION" = "latest" ]; then
  echo "Installing latest LTS Node.js via nvm..."
  nvm install --lts
  nvm alias default "lts/*"
else
  echo "Installing Node.js $VERSION via nvm..."
  nvm install "$VERSION"
  nvm alias default "$VERSION"
fi

echo "Node.js installation complete."
