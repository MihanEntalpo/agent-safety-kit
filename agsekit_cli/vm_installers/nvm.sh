#!/usr/bin/env bash
set -euo pipefail

NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

if [ -s "$NVM_DIR/nvm.sh" ]; then
  echo "nvm is already installed."
else
  echo "Installing nvm into $NVM_DIR..."
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
fi

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

ensure_line "export NVM_DIR=\"$NVM_DIR\"" "$HOME/.profile"
ensure_line "[ -s \"$NVM_DIR/nvm.sh\" ] && . \"$NVM_DIR/nvm.sh\"" "$HOME/.profile"

ensure_line "export NVM_DIR=\"$NVM_DIR\"" "$HOME/.bashrc"
ensure_line "[ -s \"$NVM_DIR/nvm.sh\" ] && . \"$NVM_DIR/nvm.sh\"" "$HOME/.bashrc"

ensure_line "export NVM_DIR=\"$NVM_DIR\"" "$HOME/.bash_profile"
ensure_line "[ -s \"$NVM_DIR/nvm.sh\" ] && . \"$NVM_DIR/nvm.sh\"" "$HOME/.bash_profile"

echo "nvm setup complete."
