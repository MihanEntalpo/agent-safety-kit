#!/usr/bin/env bash

set -euo pipefail

INSTALL_ROOT="${HOME}/.local/share/agsekit"
VENV_PATH="${INSTALL_ROOT}/venv"
BIN_DIR="${HOME}/.local/bin"
AGSEKIT_SYMLINK="${BIN_DIR}/agsekit"
AGSEKIT_BIN="${VENV_PATH}/bin/agsekit"
MULTIPASS_SYMLINK="${BIN_DIR}/multipass"
DEFAULT_WSL_MULTIPASS_EXE="/mnt/c/Program Files/Multipass/bin/multipass.exe"

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

info() {
    printf '%s\n' "$*"
}

warn() {
    printf 'Warning: %s\n' "$*" >&2
}

require_home() {
    if [ -z "${HOME:-}" ]; then
        die "HOME is not set."
    fi
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "$1 is required for this cleanup script."
}

is_wsl() {
    if [ -r /proc/sys/kernel/osrelease ]; then
        if grep -iE 'microsoft|wsl' /proc/sys/kernel/osrelease >/dev/null 2>&1; then
            return 0
        fi
    fi

    if [ -r /proc/version ]; then
        if grep -iE 'microsoft|wsl' /proc/version >/dev/null 2>&1; then
            return 0
        fi
    fi

    return 1
}

confirm_or_exit() {
    printf '\nType exactly "yes" to continue: '
    read -r answer
    if [ "$answer" != "yes" ]; then
        info "Aborted."
        exit 0
    fi
}

resolve_path() {
    local path=$1

    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$path"
    elif command -v perl >/dev/null 2>&1; then
        perl -MCwd=realpath -e 'print((realpath($ARGV[0]) || $ARGV[0]) . "\n")' "$path"
    else
        printf '%s\n' "$path"
    fi
}

same_resolved_path() {
    [ "$(resolve_path "$1")" = "$(resolve_path "$2")" ]
}

remove_install_sh_agsekit() {
    info ""
    info "Checking install.sh-managed agsekit installation..."

    if ! found_agsekit=$(command -v agsekit 2>/dev/null); then
        info "agsekit was not found in PATH."
        return 0
    fi

    if [ "$found_agsekit" != "$AGSEKIT_SYMLINK" ] && ! same_resolved_path "$found_agsekit" "$AGSEKIT_BIN"; then
        info "Skipping agsekit at $found_agsekit because it is not managed by scripts/install/install.sh."
        return 0
    fi

    if [ -L "$AGSEKIT_SYMLINK" ]; then
        local link_target
        link_target=$(readlink "$AGSEKIT_SYMLINK")
        if [ "$link_target" != "$AGSEKIT_BIN" ] && ! same_resolved_path "$AGSEKIT_SYMLINK" "$AGSEKIT_BIN"; then
            info "Skipping $AGSEKIT_SYMLINK because it does not point to $AGSEKIT_BIN."
            return 0
        fi
    elif [ -e "$AGSEKIT_SYMLINK" ]; then
        info "Skipping $AGSEKIT_SYMLINK because it is not a symlink."
        return 0
    fi

    if [ -x "${VENV_PATH}/bin/python" ] && [ -f "${VENV_PATH}/pyvenv.cfg" ]; then
        info "Uninstalling agsekit from $VENV_PATH..."
        "${VENV_PATH}/bin/python" -m pip uninstall -y agsekit || warn "pip uninstall failed; continuing with venv removal."
    else
        info "Expected venv was not found at $VENV_PATH."
    fi

    if [ -L "$AGSEKIT_SYMLINK" ]; then
        info "Removing symlink: $AGSEKIT_SYMLINK"
        rm -f "$AGSEKIT_SYMLINK"
    fi

    if [ -d "$VENV_PATH" ] && [ -f "${VENV_PATH}/pyvenv.cfg" ]; then
        info "Removing venv: $VENV_PATH"
        rm -rf "$VENV_PATH"
    fi

    if [ -d "$INSTALL_ROOT" ]; then
        rmdir "$INSTALL_ROOT" 2>/dev/null || true
    fi
}

remove_wsl_multipass_symlink() {
    info ""
    info "Checking WSL Multipass symlink..."

    if [ ! -L "$MULTIPASS_SYMLINK" ]; then
        info "No WSL Multipass symlink found at $MULTIPASS_SYMLINK."
        return 0
    fi

    local target
    target=$(readlink "$MULTIPASS_SYMLINK")
    case "$target" in
        "$DEFAULT_WSL_MULTIPASS_EXE" | *'/Multipass/bin/multipass.exe')
            info "Removing WSL Multipass symlink: $MULTIPASS_SYMLINK -> $target"
            rm -f "$MULTIPASS_SYMLINK"
            ;;
        *)
            info "Skipping $MULTIPASS_SYMLINK because it does not look like the install.sh Multipass symlink."
            ;;
    esac
}

apt_package_installed() {
    dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -Fq "install ok installed"
}

apt_package_is_manual() {
    apt-mark showmanual 2>/dev/null | grep -Fxq "$1"
}

apt_package_is_auto() {
    apt-mark showauto 2>/dev/null | grep -Fxq "$1"
}

remove_debian_auto_packages() {
    local pkg
    local -a remove_packages=()

    for pkg in "$@"; do
        if ! apt_package_installed "$pkg"; then
            info "apt package is not installed: $pkg"
        elif apt_package_is_manual "$pkg"; then
            info "Keeping manually installed apt package: $pkg"
        elif apt_package_is_auto "$pkg"; then
            info "Scheduling auto-installed apt package for removal: $pkg"
            remove_packages+=("$pkg")
        else
            info "Keeping apt package with unknown install reason: $pkg"
        fi
    done

    if [ "${#remove_packages[@]}" -eq 0 ]; then
        info "No auto-installed apt packages to remove."
        return 0
    fi

    sudo DEBIAN_FRONTEND=noninteractive apt-get purge -y "${remove_packages[@]}"
    sudo DEBIAN_FRONTEND=noninteractive apt-get autoremove --purge -y
}

remove_snap_multipass_if_present() {
    if ! command -v snap >/dev/null 2>&1; then
        info "snap is not available."
        return 0
    fi

    if snap list multipass >/dev/null 2>&1; then
        info "Removing snap package: multipass"
        sudo snap remove multipass
    else
        info "snap package multipass is not installed."
    fi
}

pacman_package_installed() {
    pacman -Q "$1" >/dev/null 2>&1
}

pacman_package_is_dependency() {
    LC_ALL=C pacman -Qi "$1" 2>/dev/null | grep -Fq "Install Reason     : Installed as a dependency"
}

remove_arch_dependency_packages() {
    local pkg
    local -a remove_packages=()

    for pkg in "$@"; do
        if ! pacman_package_installed "$pkg"; then
            info "pacman package is not installed: $pkg"
        elif pacman_package_is_dependency "$pkg"; then
            info "Scheduling dependency-installed pacman package for removal: $pkg"
            remove_packages+=("$pkg")
        else
            info "Keeping explicitly installed pacman package: $pkg"
        fi
    done

    if [ "${#remove_packages[@]}" -eq 0 ]; then
        info "No dependency-installed pacman packages to remove."
        return 0
    fi

    if ! sudo pacman -Rns --noconfirm "${remove_packages[@]}"; then
        warn "pacman refused to remove at least one package, probably because it is still required."
    fi
}

brew_formula_installed() {
    brew list --formula "$1" >/dev/null 2>&1
}

brew_cask_installed() {
    brew list --cask "$1" >/dev/null 2>&1
}

remove_brew_formula_if_installed() {
    local pkg=$1
    if brew_formula_installed "$pkg"; then
        info "Removing Homebrew formula: $pkg"
        brew uninstall "$pkg"
    else
        info "Homebrew formula is not installed: $pkg"
    fi
}

remove_brew_cask_if_installed() {
    local pkg=$1
    if brew_cask_installed "$pkg"; then
        info "Removing Homebrew cask: $pkg"
        brew uninstall --cask "$pkg"
    else
        info "Homebrew cask is not installed: $pkg"
    fi
}
