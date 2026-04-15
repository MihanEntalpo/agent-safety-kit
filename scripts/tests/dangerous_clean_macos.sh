#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./dangerous_clean_common.sh
. "$SCRIPT_DIR/dangerous_clean_common.sh"

main() {
    require_home

    if [ "$(uname -s)" != "Darwin" ]; then
        die "This script is intended for macOS."
    fi

    require_command brew

    cat <<EOF
Dangerous macOS cleanup for developer test machines only.

This script will:
- remove Homebrew formula "multipass" if it is installed
- remove Homebrew cask "multipass" if it is installed
- remove Homebrew formula "rsync" if it is installed
- remove agsekit only if it matches the scripts/install/install.sh layout:
  $AGSEKIT_SYMLINK -> $AGSEKIT_BIN
  $VENV_PATH

It may ask for administrator credentials through Homebrew. Do not run it on a
machine you are not prepared to repair.
EOF

    confirm_or_exit

    remove_brew_formula_if_installed multipass
    remove_brew_cask_if_installed multipass
    remove_brew_formula_if_installed rsync
    remove_install_sh_agsekit
}

main "$@"
