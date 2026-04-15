#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./dangerous_clean_common.sh
. "$SCRIPT_DIR/dangerous_clean_common.sh"

WSL_PREPARE_PACKAGES=(
    snapd
    qemu-kvm
    libvirt-daemon-system
    libvirt-clients
    bridge-utils
    openssh-client
    rsync
)

main() {
    require_home
    require_command apt-get
    require_command apt-mark
    require_command dpkg-query

    if ! is_wsl; then
        die "This script is intended for WSL. Use the Debian script for regular Debian/Ubuntu hosts."
    fi

    cat <<EOF
Dangerous WSL cleanup for developer test machines only.

This script will:
- inspect these apt packages:
  ${WSL_PREPARE_PACKAGES[*]}
- purge only apt packages from that list that are installed as auto/dependency packages
- keep apt packages from that list if they are marked as manually installed
- run apt-get autoremove --purge after package removal
- remove the WSL-side Multipass symlink at $MULTIPASS_SYMLINK only if it points to a Windows multipass.exe
- not remove Multipass from Windows itself
- remove agsekit only if it matches the scripts/install/install.sh layout:
  $AGSEKIT_SYMLINK -> $AGSEKIT_BIN
  $VENV_PATH

It may ask for sudo. Do not run it on a machine you are not prepared to repair.
EOF

    confirm_or_exit

    remove_debian_auto_packages "${WSL_PREPARE_PACKAGES[@]}"
    remove_wsl_multipass_symlink
    remove_install_sh_agsekit
}

main "$@"
