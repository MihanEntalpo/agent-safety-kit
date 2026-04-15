#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./dangerous_clean_common.sh
. "$SCRIPT_DIR/dangerous_clean_common.sh"

DEBIAN_PREPARE_PACKAGES=(
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

    if is_wsl; then
        die "WSL detected. Use dangerous_clean_wsl.sh instead."
    fi

    cat <<EOF
Dangerous Debian cleanup for developer test machines only.

This script will:
- remove the snap package "multipass" if it is installed
- inspect these apt packages:
  ${DEBIAN_PREPARE_PACKAGES[*]}
- purge only apt packages from that list that are installed as auto/dependency packages
- keep apt packages from that list if they are marked as manually installed
- run apt-get autoremove --purge after package removal
- remove agsekit only if it matches the scripts/install/install.sh layout:
  $AGSEKIT_SYMLINK -> $AGSEKIT_BIN
  $VENV_PATH

It may ask for sudo. Do not run it on a machine you are not prepared to repair.
EOF

    confirm_or_exit

    remove_snap_multipass_if_present
    remove_debian_auto_packages "${DEBIAN_PREPARE_PACKAGES[@]}"
    remove_install_sh_agsekit
}

main "$@"
