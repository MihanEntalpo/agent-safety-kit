#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./dangerous_clean_common.sh
. "$SCRIPT_DIR/dangerous_clean_common.sh"

ARCH_PREPARE_PACKAGES=(
    multipass
    libvirt
    dnsmasq
    qemu-base
    openssh
    rsync
)

main() {
    require_home
    require_command pacman

    if is_wsl; then
        die "WSL detected. Use dangerous_clean_wsl.sh instead."
    fi

    cat <<EOF
Dangerous Arch Linux cleanup for developer test machines only.

This script will:
- inspect these pacman packages:
  ${ARCH_PREPARE_PACKAGES[*]}
- remove only packages from that list whose pacman install reason is "dependency"
- keep packages from that list if they are explicitly installed
- remove orphaned dependencies of removed packages with pacman -Rns
- remove agsekit only if it matches the scripts/install/install.sh layout:
  $AGSEKIT_SYMLINK -> $AGSEKIT_BIN
  $VENV_PATH

It may ask for sudo. Do not run it on a machine you are not prepared to repair.
EOF

    confirm_or_exit

    remove_arch_dependency_packages "${ARCH_PREPARE_PACKAGES[@]}"
    remove_install_sh_agsekit
}

main "$@"
