#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-latest}"
PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"

if ! command -v pyenv >/dev/null 2>&1; then
  echo "pyenv is not installed. Install the pyenv bundle first." >&2
  exit 1
fi

export PYENV_ROOT="$PYENV_ROOT"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

if [ "$VERSION" = "latest" ]; then
  VERSION=$(pyenv install -l | sed 's/^ *//' | grep -E '^[0-9]+(\.[0-9]+)*$' | tail -1)
fi

if [ -z "$VERSION" ]; then
  echo "Unable to resolve a Python version to install." >&2
  exit 1
fi

echo "Installing Python $VERSION via pyenv (skip if already present)..."
pyenv install --skip-existing "$VERSION"
pyenv global "$VERSION"

echo "Python $VERSION is ready."
