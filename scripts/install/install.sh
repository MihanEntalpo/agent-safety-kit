#!/bin/sh
# Installer for curl -fsSL https://agsekit.org/install.sh | sh

set -eu

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

info() {
    printf '%s\n' "$*"
}

prompt_yes_no() {
    PROMPT_MESSAGE=$1
    DEFAULT_ANSWER=${2:-yes}

    if [ ! -r /dev/tty ] || [ ! -w /dev/tty ]; then
        die "An interactive terminal is required to confirm automatic Python installation. Install Python 3.9+ manually, then rerun this installer."
    fi

    while :; do
        case "$DEFAULT_ANSWER" in
            yes)
                PROMPT_SUFFIX='[Y/n]'
                ;;
            no)
                PROMPT_SUFFIX='[y/N]'
                ;;
            *)
                die "Unsupported default answer for prompt: $DEFAULT_ANSWER"
                ;;
        esac

        printf '%s %s ' "$PROMPT_MESSAGE" "$PROMPT_SUFFIX" > /dev/tty
        if ! IFS= read -r PROMPT_ANSWER < /dev/tty; then
            die "Could not read a response from the terminal."
        fi

        case "$PROMPT_ANSWER" in
            '')
                if [ "$DEFAULT_ANSWER" = yes ]; then
                    return 0
                fi
                return 1
                ;;
            [Yy]|[Yy][Ee][Ss])
                return 0
                ;;
            [Nn]|[Nn][Oo])
                return 1
                ;;
            *)
                info "Please answer y or n."
                ;;
        esac
    done
}

run_elevated() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
        return
    fi

    if command -v sudo >/dev/null 2>&1; then
        sudo "$@"
        return
    fi

    die "Automatic Python installation requires root privileges. Re-run this installer as root or install sudo."
}

require_home() {
    if [ -z "${HOME:-}" ]; then
        die "HOME is not set."
    fi
}

is_wsl() {
    if [ -r /proc/sys/kernel/osrelease ]; then
        if grep -i microsoft /proc/sys/kernel/osrelease >/dev/null 2>&1 || grep -i wsl /proc/sys/kernel/osrelease >/dev/null 2>&1; then
            return 0
        fi
    fi

    if [ -r /proc/version ]; then
        if grep -i microsoft /proc/version >/dev/null 2>&1 || grep -i wsl /proc/version >/dev/null 2>&1; then
            return 0
        fi
    fi

    return 1
}

detect_platform() {
    UNAME_S=$(uname -s 2>/dev/null || printf 'unknown')

    case "$UNAME_S" in
        Darwin)
            PLATFORM=macos
            ;;
        Linux)
            if is_wsl; then
                PLATFORM=wsl
            else
                PLATFORM=linux
            fi
            ;;
        *)
            die "Unsupported OS: $UNAME_S. Supported platforms: Linux, macOS, WSL."
            ;;
    esac
}

find_python() {
    PYTHON_BIN=""
    PYTHON_VERSION=""
    FOUND_UNSUPPORTED_BIN=""
    FOUND_UNSUPPORTED_VERSION=""

    for PYTHON_CANDIDATE in python3 python; do
        PYTHON_PATH=$(command -v "$PYTHON_CANDIDATE" 2>/dev/null || printf '')
        if [ -z "$PYTHON_PATH" ]; then
            continue
        fi

        CANDIDATE_VERSION=$("$PYTHON_PATH" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || printf '')
        if [ -z "$CANDIDATE_VERSION" ]; then
            continue
        fi

        if "$PYTHON_PATH" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
            PYTHON_BIN=$PYTHON_PATH
            PYTHON_VERSION=$CANDIDATE_VERSION
            return 0
        fi

        if [ -z "$FOUND_UNSUPPORTED_BIN" ]; then
            FOUND_UNSUPPORTED_BIN=$PYTHON_PATH
            FOUND_UNSUPPORTED_VERSION=$CANDIDATE_VERSION
        fi
    done

    if [ -n "$FOUND_UNSUPPORTED_BIN" ]; then
        PYTHON_BIN=$FOUND_UNSUPPORTED_BIN
        PYTHON_VERSION=$FOUND_UNSUPPORTED_VERSION
        return 2
    fi

    return 1
}

install_linux_packages() {
    if command -v apt-get >/dev/null 2>&1; then
        run_elevated apt-get update
        run_elevated apt-get install -y "$@"
        return 0
    fi

    if command -v pacman >/dev/null 2>&1; then
        run_elevated pacman -Sy --needed --noconfirm "$@"
        return 0
    fi

    return 1
}

install_python_on_linux() {
    if command -v apt-get >/dev/null 2>&1; then
        info "Installing Python 3.9+ with apt..."
        install_linux_packages --reinstall python3 python3-pip python3-venv
        return 0
    fi

    if command -v pacman >/dev/null 2>&1; then
        info "Installing Python 3.9+ with pacman..."
        install_linux_packages python python-pip
        return 0
    fi

    die "Automatic Python installation on Linux is supported only for Debian/Ubuntu (apt) and Arch (pacman). Install Python 3.9+ manually, then rerun this installer."
}

install_python_support_on_linux() {
    if command -v apt-get >/dev/null 2>&1; then
        info "Installing missing Python venv support with apt..."
        install_linux_packages python3-pip python3-venv
        return 0
    fi

    if command -v pacman >/dev/null 2>&1; then
        info "Installing missing Python venv support with pacman..."
        install_linux_packages python-pip
        return 0
    fi

    return 1
}

install_python_on_macos() {
    if ! command -v brew >/dev/null 2>&1; then
        die "Homebrew is required to install Python automatically on macOS. Install Homebrew from https://brew.sh/ and rerun this installer."
    fi

    info "Installing Python 3.9+ with Homebrew..."
    brew install python
}

ensure_python() {
    if find_python; then
        return 0
    fi

    FIND_PYTHON_STATUS=$?
    if [ "$FIND_PYTHON_STATUS" -eq 2 ]; then
        die "Python 3.9+ is required; found Python $PYTHON_VERSION at $PYTHON_BIN. Install Python 3.9 or newer first, then rerun this installer."
    fi

    if ! prompt_yes_no "Python 3.9+ was not found. Install it automatically now?" yes; then
        die "Python 3.9+ is required. Install Python 3.9 or newer first, then rerun this installer."
    fi

    case "$PLATFORM" in
        linux|wsl)
            install_python_on_linux
            ;;
        macos)
            install_python_on_macos
            ;;
        *)
            die "Automatic Python installation is not supported on platform: $PLATFORM"
            ;;
    esac

    if find_python; then
        return 0
    fi

    FIND_PYTHON_STATUS=$?
    if [ "$FIND_PYTHON_STATUS" -eq 2 ]; then
        die "Automatic Python installation completed, but the detected Python version is still unsupported: $PYTHON_VERSION"
    fi

    die "Automatic Python installation completed, but Python 3.9+ is still not available in PATH. Open a new shell and rerun this installer."
}

create_or_update_venv() {
    mkdir -p "$INSTALL_ROOT"

    if ! "$PYTHON_BIN" -m venv "$VENV_PATH"; then
        if [ "$PLATFORM" = linux ] || [ "$PLATFORM" = wsl ]; then
            if install_python_support_on_linux && "$PYTHON_BIN" -m venv "$VENV_PATH"; then
                :
            else
                die "Failed to create venv at $VENV_PATH. Ensure Python venv support is installed for Python 3.9+."
            fi
        else
            die "Failed to create venv at $VENV_PATH. Ensure Python venv support is installed for Python 3.9+."
        fi
    fi

    if [ ! -d "$VENV_PATH" ]; then
        die "Failed to create venv at $VENV_PATH. Ensure Python venv support is installed for Python 3.9+."
    fi

    VENV_PYTHON="$VENV_PATH/bin/python"

    if [ ! -x "$VENV_PYTHON" ]; then
        die "Venv Python was not created at $VENV_PYTHON."
    fi
}

install_package() {
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install --upgrade "$AGSEKIT_PACKAGE"

    if [ ! -x "$AGSEKIT_BIN" ]; then
        die "agsekit executable was not found at $AGSEKIT_BIN after installation."
    fi
}

create_or_update_symlink() {
    mkdir -p "$BIN_DIR"

    if [ -e "$SYMLINK_PATH" ] || [ -L "$SYMLINK_PATH" ]; then
        if [ ! -L "$SYMLINK_PATH" ]; then
            die "Refusing to replace non-symlink path: $SYMLINK_PATH"
        fi
        rm -f "$SYMLINK_PATH"
    fi

    ln -s "$AGSEKIT_BIN" "$SYMLINK_PATH"
}

path_contains_bin_dir() {
    case ":${PATH:-}:" in
        *":$BIN_DIR:"*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

add_path_line() {
    RC_FILE=$1
    RC_DIR=${RC_FILE%/*}

    mkdir -p "$RC_DIR"

    if [ -f "$RC_FILE" ] && grep -F -x "$PATH_LINE" "$RC_FILE" >/dev/null 2>&1; then
        return 0
    fi

    printf '\n%s\n' "$PATH_LINE" >> "$RC_FILE"
    PATH_FILES_CHANGED=1
}

add_path_line_to_files() {
    for RC_TARGET in "$@"; do
        add_path_line "$RC_TARGET"
    done
}

configure_path() {
    PATH_HINT_NEEDED=0
    PATH_FILES_CHANGED=0

    if path_contains_bin_dir; then
        return 0
    fi

    PATH_HINT_NEEDED=1
    SHELL_NAME=unknown
    if [ -n "${SHELL:-}" ]; then
        SHELL_NAME=${SHELL##*/}
    fi

    case "$SHELL_NAME" in
        zsh)
            if [ "$PLATFORM" = macos ]; then
                add_path_line_to_files "$HOME/.zprofile" "$HOME/.zshrc"
            else
                add_path_line_to_files "$HOME/.zshrc"
            fi
            ;;
        bash)
            add_path_line_to_files "$HOME/.bashrc" "$HOME/.profile"
            ;;
        *)
            add_path_line_to_files "$HOME/.profile"
            ;;
    esac
}

find_wsl_multipass_exe() {
    WSL_MULTIPASS_EXE=""
    WSL_MULTIPASS_EXE_FOUND=0

    if FOUND_MULTIPASS_EXE=$(command -v multipass.exe 2>/dev/null); then
        if [ -n "$FOUND_MULTIPASS_EXE" ]; then
            WSL_MULTIPASS_EXE=$FOUND_MULTIPASS_EXE
            WSL_MULTIPASS_EXE_FOUND=1
            return 0
        fi
    fi

    DEFAULT_MULTIPASS_EXE=${WSL_MULTIPASS_EXE_FALLBACK:-"/mnt/c/Program Files/Multipass/bin/multipass.exe"}
    WSL_MULTIPASS_EXE=$DEFAULT_MULTIPASS_EXE
    if [ -f "$DEFAULT_MULTIPASS_EXE" ]; then
        WSL_MULTIPASS_EXE_FOUND=1
        return 0
    fi

    return 1
}

create_or_update_wsl_multipass_symlink() {
    MULTIPASS_SYMLINK_CHANGED=0
    WSL_MULTIPASS_WARNING_NEEDED=0

    if [ "$PLATFORM" != wsl ]; then
        return 0
    fi

    if ! find_wsl_multipass_exe; then
        WSL_MULTIPASS_WARNING_NEEDED=1
    fi

    mkdir -p "$BIN_DIR"

    if [ -e "$MULTIPASS_SYMLINK_PATH" ] || [ -L "$MULTIPASS_SYMLINK_PATH" ]; then
        if [ ! -L "$MULTIPASS_SYMLINK_PATH" ]; then
            die "Refusing to replace non-symlink path: $MULTIPASS_SYMLINK_PATH"
        fi

        CURRENT_MULTIPASS_TARGET=$(readlink "$MULTIPASS_SYMLINK_PATH" 2>/dev/null || printf '')
        if [ "$CURRENT_MULTIPASS_TARGET" = "$WSL_MULTIPASS_EXE" ]; then
            return 0
        fi

        rm -f "$MULTIPASS_SYMLINK_PATH"
    fi

    ln -s "$WSL_MULTIPASS_EXE" "$MULTIPASS_SYMLINK_PATH"
    MULTIPASS_SYMLINK_CHANGED=1
}

print_summary() {
    info ""
    info "agsekit installed."
    info "Install directory: $INSTALL_ROOT"
    info "Command symlink: $SYMLINK_PATH"
    info "Detected platform: $PLATFORM"

    if [ "$PATH_HINT_NEEDED" -eq 1 ]; then
        info ""
        if [ "$PATH_FILES_CHANGED" -eq 1 ]; then
            info "PATH was updated in shell startup files."
        else
            info "PATH is already configured in shell startup files."
        fi
        info "For the current shell session, run:"
        info 'export PATH="$HOME/.local/bin:$PATH"'
    fi

    if [ "$PLATFORM" = wsl ]; then
        info ""
        if [ "$MULTIPASS_SYMLINK_CHANGED" -eq 1 ]; then
            info "WSL Multipass symlink was created."
        else
            info "WSL Multipass symlink is already configured."
        fi
        info "Multipass symlink: $MULTIPASS_SYMLINK_PATH -> $WSL_MULTIPASS_EXE"
        if [ "$WSL_MULTIPASS_WARNING_NEEDED" -eq 1 ]; then
            info ""
            info "Внимание! Multipass не установлен! Установите его скачав по ссылке $MULTIPASS_WINDOWS_INSTALL_URL"
        fi
    fi
}

main() {
    require_home
    detect_platform
    ensure_python

    INSTALL_ROOT="$HOME/.local/share/agsekit"
    VENV_PATH="$INSTALL_ROOT/venv"
    BIN_DIR="$HOME/.local/bin"
    SYMLINK_PATH="$BIN_DIR/agsekit"
    MULTIPASS_SYMLINK_PATH="$BIN_DIR/multipass"
    AGSEKIT_BIN="$VENV_PATH/bin/agsekit"
    PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
    MULTIPASS_WINDOWS_INSTALL_URL="https://canonical.com/multipass/install"
    AGSEKIT_PACKAGE=${AGSEKIT_PACKAGE:-agsekit}

    info "Installing agsekit..."
    info "Package: $AGSEKIT_PACKAGE"
    info "Python: $PYTHON_BIN ($PYTHON_VERSION)"

    create_or_update_venv
    install_package
    create_or_update_symlink
    configure_path
    create_or_update_wsl_multipass_symlink
    print_summary
}

main "$@"
