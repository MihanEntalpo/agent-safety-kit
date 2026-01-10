#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/proxychains_common.sh"

PROXYCHAINS_PROXY="${AGSEKIT_PROXYCHAINS_PROXY:-}"

echo "Installing Claude Code agent..."

run_with_proxychains curl -fsSL https://claude.ai/install.sh | bash
