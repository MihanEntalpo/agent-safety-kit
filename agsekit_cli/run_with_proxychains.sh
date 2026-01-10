#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF' 1>&2
Usage: ./run_with_proxychains.sh --proxy <scheme://host:port> <program> [args...]

Creates a temporary proxychains4 config for the provided proxy and executes the program through proxychains4.
EOF
  exit 2
}

proxy_setting=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --proxy)
      shift
      [[ $# -gt 0 ]] || usage
      proxy_setting="$1"
      shift
      ;;
    --help|-h)
      usage
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

[[ -n "$proxy_setting" ]] || usage
[[ $# -gt 0 ]] || usage

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/agent_scripts/proxychains_common.sh"

PROXYCHAINS_PROXY="$proxy_setting"
PROXYCHAINS_QUIET=1

run_with_proxychains "$@"
