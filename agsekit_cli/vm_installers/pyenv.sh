#!/usr/bin/env bash
set -euo pipefail

PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"

if command -v pyenv >/dev/null 2>&1; then
  echo "pyenv is already installed."
else
  echo "Installing pyenv build dependencies..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    curl \
    git \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev

  echo "Installing pyenv into $PYENV_ROOT..."
  curl -fsSL https://pyenv.run | bash
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

ensure_line "export PYENV_ROOT=\"$PYENV_ROOT\"" "$HOME/.profile"
ensure_line "export PATH=\"$PYENV_ROOT/bin:\$PATH\"" "$HOME/.profile"
ensure_line "eval \"\$(pyenv init -)\"" "$HOME/.profile"

ensure_line "export PYENV_ROOT=\"$PYENV_ROOT\"" "$HOME/.bashrc"
ensure_line "export PATH=\"$PYENV_ROOT/bin:\$PATH\"" "$HOME/.bashrc"
ensure_line "eval \"\$(pyenv init -)\"" "$HOME/.bashrc"

ensure_line "export PYENV_ROOT=\"$PYENV_ROOT\"" "$HOME/.bash_profile"
ensure_line "export PATH=\"$PYENV_ROOT/bin:\$PATH\"" "$HOME/.bash_profile"
ensure_line "eval \"\$(pyenv init -)\"" "$HOME/.bash_profile"

echo "pyenv setup complete."
