#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/proxychains_common.sh"

PROXYCHAINS_PROXY="${AGSEKIT_PROXYCHAINS_PROXY:-}"
SWAP_FILE=""
SWAP_CREATED=0
BUILD_ROOT=""
INSTALL_SUCCESS=0
INSTALLED_CODEX_PATH=""


run_privileged() {
  if command -v sudo >/dev/null 2>&1 && [ "$(id -u)" -ne 0 ]; then
    sudo "$@"
  else
    "$@"
  fi
}

cleanup_swap() {
  if [ "$SWAP_CREATED" -eq 1 ] && [ -n "${SWAP_FILE:-}" ]; then
    echo "отключаю и удаляю временный swap-файл ${SWAP_FILE}"
    run_privileged swapoff "$SWAP_FILE" 2>/dev/null || true
    run_privileged rm -f "$SWAP_FILE"
    SWAP_CREATED=0
    SWAP_FILE=""
  fi
}

cleanup() {
  cleanup_swap
  if [ -n "${BUILD_ROOT:-}" ]; then
    if [ -n "$INSTALLED_CODEX_PATH" ] && [ -x "$INSTALLED_CODEX_PATH" ]; then
      if "$INSTALLED_CODEX_PATH" --version >/dev/null 2>&1; then
        rm -rf "$BUILD_ROOT"
      else
        echo "codex-glibc is unavailable or not runnable, keeping build directory at ${BUILD_ROOT}"
      fi
    else
      echo "codex-glibc is unavailable or not runnable, keeping build directory at ${BUILD_ROOT}"
    fi
  fi
}

ensure_swap_for_build() {
  local min_free_kb mem_available_kb swap_free_kb total_free_kb needed_kb swap_bytes swap_mb
  min_free_kb=$((3 * 1024 * 1024))
  mem_available_kb="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
  swap_free_kb="$(awk '/SwapFree:/ {print $2}' /proc/meminfo)"
  mem_available_kb="${mem_available_kb:-0}"
  swap_free_kb="${swap_free_kb:-0}"
  total_free_kb=$((mem_available_kb + swap_free_kb))

  if [ "$total_free_kb" -ge "$min_free_kb" ]; then
    echo "Checking available RAM: there is enough RAM to build codex-glibc."
    return
  fi

  needed_kb=$((min_free_kb - total_free_kb))
  swap_bytes=$((needed_kb * 1024))
  swap_mb=$(((needed_kb + 1023) / 1024))

  echo "Not enough RAM to build codex-glibc, creating a swap file."

  if command -v sudo >/dev/null 2>&1 && [ "$(id -u)" -ne 0 ]; then
    SWAP_FILE="$(sudo mktemp --tmpdir=/ codex-glibc-swap-XXXXXX)"
  else
    SWAP_FILE="$(mktemp --tmpdir=/ codex-glibc-swap-XXXXXX)"
  fi

  if command -v fallocate >/dev/null 2>&1; then
    run_privileged fallocate -l "$swap_bytes" "$SWAP_FILE"
  else
    run_privileged dd if=/dev/zero of="$SWAP_FILE" bs=1M count="$swap_mb" status=none
  fi

  run_privileged chmod 600 "$SWAP_FILE"
  run_privileged mkswap "$SWAP_FILE" >/dev/null
  run_privileged swapon "$SWAP_FILE"
  SWAP_CREATED=1
}

trap cleanup EXIT INT TERM

echo "Building Codex agent with glibc toolchain..."

ensure_swap_for_build

sudo apt-get update -y
sudo apt-get install -y build-essential pkg-config libssl-dev curl git

if ! command -v rustup >/dev/null 2>&1; then
  echo "Installing Rust toolchain via rustup..."
  RUSTUP_INSTALLER="$(mktemp -t rustup-init-XXXXXX.sh)"
  echo "Downloading rustup installer to $RUSTUP_INSTALLER ..."
  run_with_proxychains curl --proto '=https' --tlsv1.2 -fL https://sh.rustup.rs -o "$RUSTUP_INSTALLER"
  echo "Running rustup installer in batch mode (-y)..."
  export RUSTUP_INIT_SKIP_PATH_CHECK=yes
  ( set -x; sh "$RUSTUP_INSTALLER" -y --no-modify-path )
  rm -f "$RUSTUP_INSTALLER"
  echo "Rustup installation finished."
fi

if [ -f "$HOME/.cargo/env" ]; then
  # shellcheck disable=SC1090
  . "$HOME/.cargo/env"
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "Cargo is unavailable after rustup installation. Please check your Rust setup."
  exit 1
fi

HOST_TARGET="$(rustc -Vv | awk '/host:/ {print $2}')"
if [ -z "$HOST_TARGET" ]; then
  ARCH="$(uname -m)"
  HOST_TARGET="${ARCH}-unknown-linux-gnu"
fi

run_with_proxychains rustup target add "$HOST_TARGET"

BUILD_ROOT="$(mktemp -d -t codex-src-XXXXXX)"

echo "Cloning codex repository..."
run_with_proxychains git clone --depth 1 https://github.com/openai/codex.git "$BUILD_ROOT/codex"

MANIFEST_PATH="$(
  python3 - "$BUILD_ROOT/codex" <<'PYCODE'
import pathlib
import sys
import tomllib

root = pathlib.Path(sys.argv[1])
candidates = []

for path in root.rglob("Cargo.toml"):
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue

    pkg_name = data.get("package", {}).get("name")
    bins = data.get("bin", []) or []
    has_codex_bin = any(isinstance(item, dict) and item.get("name") == "codex" for item in bins)
    score = 0
    if pkg_name == "codex-cli":
        score = 3
    elif has_codex_bin:
        score = 2
    elif pkg_name == "codex":
        score = 1

    if score:
        candidates.append((score, len(path.parts), str(path)))

if not candidates:
    sys.exit(0)

best = sorted(candidates, key=lambda item: (-item[0], item[1]))[0]
print(best[2])
PYCODE
)"

if [ -z "$MANIFEST_PATH" ]; then
  echo "Unable to locate Cargo.toml for codex build."
  exit 1
fi

echo "Compiling codex for target ${HOST_TARGET}..."
echo "Using Cargo manifest at ${MANIFEST_PATH}."
CARGO_CACHE_ROOT="${HOME}/.tmp/build-codex-glibc"
export CARGO_TARGET_DIR="${CARGO_CACHE_ROOT}/target"
mkdir -p "$CARGO_TARGET_DIR"
export CARGO_BUILD_JOBS=1
export CARGO_PROFILE_RELEASE_LTO=off
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1
export CARGO_PROFILE_RELEASE_DEBUG=false
run_with_proxychains cargo build --release --target "$HOST_TARGET" --manifest-path "$MANIFEST_PATH"
cleanup_swap

BUILT_BINARY="$CARGO_TARGET_DIR/$HOST_TARGET/release/codex"
if [ ! -x "$BUILT_BINARY" ]; then
  echo "Expected binary not found at $BUILT_BINARY"
  exit 1
fi

DEST_PATH="/usr/local/bin/codex-glibc"
if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  sudo install -m 0755 "$BUILT_BINARY" "$DEST_PATH"
  echo "Installed codex-glibc to $DEST_PATH using sudo."
  INSTALLED_CODEX_PATH="$DEST_PATH"
else
  mkdir -p "$HOME/.local/bin"
  install -m 0755 "$BUILT_BINARY" "$HOME/.local/bin/codex-glibc"
  DEST_PATH="$HOME/.local/bin/codex-glibc"
  INSTALLED_CODEX_PATH="$DEST_PATH"
  if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.profile" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
    echo "Added $HOME/.local/bin to PATH in ~/.profile."
  fi
  echo "Installed codex-glibc to $DEST_PATH."
fi

if "$INSTALLED_CODEX_PATH" --version >/dev/null 2>&1; then
  INSTALL_SUCCESS=1
else
  echo "codex-glibc is unavailable or not runnable after installation."
fi
