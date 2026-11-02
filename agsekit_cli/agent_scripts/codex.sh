#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/proxychains_common.sh"

PROXYCHAINS_PROXY="${AGSEKIT_PROXYCHAINS_PROXY:-}"
CODEX_RELEASE="${AGSEKIT_AGENT_VERSION:-latest}"
INSTALL_SCRIPT="$(mktemp /tmp/agsekit-codex-install-XXXXXX.sh)"

cleanup() {
  rm -f "$INSTALL_SCRIPT"
}
trap cleanup EXIT INT TERM

echo "Installing official Codex standalone package..."
run_with_proxychains curl -fsSL https://chatgpt.com/codex/install.sh -o "$INSTALL_SCRIPT"
run_with_proxychains env CODEX_NON_INTERACTIVE=1 CODEX_RELEASE="$CODEX_RELEASE" sh "$INSTALL_SCRIPT"

CODEX_PACKAGE_ROOT="$HOME/.codex/packages/standalone/current"
for required_path in \
  "$CODEX_PACKAGE_ROOT/codex-package.json" \
  "$CODEX_PACKAGE_ROOT/bin/codex" \
  "$CODEX_PACKAGE_ROOT/bin/codex-code-mode-host" \
  "$CODEX_PACKAGE_ROOT/codex-path/rg" \
  "$CODEX_PACKAGE_ROOT/codex-resources/bwrap"; do
  if [ ! -e "$required_path" ]; then
    echo "Official Codex standalone package is incomplete: $required_path is missing" >&2
    exit 1
  fi
done

"$HOME/.local/bin/codex" --version
