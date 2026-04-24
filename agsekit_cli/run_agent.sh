#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF' 1>&2
Usage:
  ./run_agent.sh --workdir <path> --binary <name> [--load-nvm] [--env KEY=VALUE ...] [--proxychains <scheme://host:port>] [--http-proxy-url <http://host:port> | --http-proxy-upstream <scheme://host:port> [--http-proxy-listen <host:port|port>] --http-proxy-pool-start <port> --http-proxy-pool-end <port>] -- <program> [args...]

Checks that the agent binary is available inside the VM, prepares the runtime environment, and then executes the provided command.
EOF
  exit 2
}

workdir=""
binary=""
load_nvm=0
proxychains_proxy=""
http_proxy_url=""
http_proxy_upstream=""
http_proxy_listen=""
http_proxy_pool_start=""
http_proxy_pool_end=""
declare -a env_exports=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workdir)
      shift
      [[ $# -gt 0 ]] || usage
      workdir="$1"
      shift
      ;;
    --binary)
      shift
      [[ $# -gt 0 ]] || usage
      binary="$1"
      shift
      ;;
    --load-nvm)
      load_nvm=1
      shift
      ;;
    --env)
      shift
      [[ $# -gt 0 ]] || usage
      env_exports+=("$1")
      shift
      ;;
    --proxychains)
      shift
      [[ $# -gt 0 ]] || usage
      proxychains_proxy="$1"
      shift
      ;;
    --http-proxy-url)
      shift
      [[ $# -gt 0 ]] || usage
      http_proxy_url="$1"
      shift
      ;;
    --http-proxy-upstream)
      shift
      [[ $# -gt 0 ]] || usage
      http_proxy_upstream="$1"
      shift
      ;;
    --http-proxy-listen)
      shift
      [[ $# -gt 0 ]] || usage
      http_proxy_listen="$1"
      shift
      ;;
    --http-proxy-pool-start)
      shift
      [[ $# -gt 0 ]] || usage
      http_proxy_pool_start="$1"
      shift
      ;;
    --http-proxy-pool-end)
      shift
      [[ $# -gt 0 ]] || usage
      http_proxy_pool_end="$1"
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

[[ -n "$workdir" ]] || usage
[[ -n "$binary" ]] || usage
[[ $# -gt 0 ]] || usage

if [[ -n "$http_proxy_url" && -n "$http_proxy_upstream" ]]; then
  echo "Only one of --http-proxy-url or --http-proxy-upstream may be used." >&2
  usage
fi

if [[ -n "$proxychains_proxy" && ( -n "$http_proxy_url" || -n "$http_proxy_upstream" ) ]]; then
  echo "proxychains and http_proxy cannot be used together." >&2
  usage
fi

if [[ -n "$http_proxy_upstream" ]]; then
  [[ -n "$http_proxy_pool_start" && -n "$http_proxy_pool_end" ]] || usage
fi

export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"

if [[ "$load_nvm" -eq 1 ]]; then
  export NVM_DIR=${NVM_DIR:-$HOME/.nvm}
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck disable=SC1090
    . "$NVM_DIR/nvm.sh"
  elif [[ -s "$NVM_DIR/bash_completion" ]]; then
    # shellcheck disable=SC1090
    . "$NVM_DIR/bash_completion"
  fi
fi

if ! command -v "$binary" >/dev/null 2>&1; then
  echo "Agent binary not found: $binary" >&2
  exit 127
fi

for entry in "${env_exports[@]}"; do
  case "$entry" in
    *=*)
      export "$entry"
      ;;
    *)
      echo "Invalid environment assignment: $entry" >&2
      exit 2
      ;;
  esac
done

if [[ ! -d "$workdir" ]]; then
  echo "Workdir does not exist inside the VM: $workdir" >&2
  exit 2
fi

cd "$workdir"

declare -a command=("$@")

if [[ -n "$http_proxy_url" ]]; then
  command=("bash" "/usr/bin/agsekit-run_with_http_proxy.sh" "--url" "$http_proxy_url" "--" "${command[@]}")
elif [[ -n "$http_proxy_upstream" ]]; then
  declare -a wrapped=(
    "bash" "/usr/bin/agsekit-run_with_http_proxy.sh"
    "--upstream" "$http_proxy_upstream"
    "--pool-start" "$http_proxy_pool_start"
    "--pool-end" "$http_proxy_pool_end"
  )
  if [[ -n "$http_proxy_listen" ]]; then
    wrapped+=("--listen" "$http_proxy_listen")
  fi
  wrapped+=("--" "${command[@]}")
  command=("${wrapped[@]}")
fi

if [[ -n "$proxychains_proxy" ]]; then
  command=("bash" "/usr/bin/agsekit-run_with_proxychains.sh" "--proxy" "$proxychains_proxy" "--" "${command[@]}")
fi

exec "${command[@]}"
