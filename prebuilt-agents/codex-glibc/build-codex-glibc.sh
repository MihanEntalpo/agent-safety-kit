#!/usr/bin/env bash
set -euo pipefail

CODEX_REPO="${CODEX_REPO:-https://github.com/openai/codex.git}"
CODEX_REF="${CODEX_REF:-}"
OUTPUT_DIR="${OUTPUT_DIR:-/out}"
RUST_TARGET="${RUST_TARGET:-x86_64-unknown-linux-gnu}"
OUTPUT_BASENAME="${OUTPUT_BASENAME:-codex-glibc-linux-amd64}"

mkdir -p "${OUTPUT_DIR}"

BUILD_ROOT="/work/codex-src"
rm -rf "${BUILD_ROOT}"
mkdir -p "${BUILD_ROOT}"

cd "${BUILD_ROOT}"

if [[ -n "${CODEX_REF}" ]]; then
  git clone --depth 1 --branch "${CODEX_REF}" --single-branch "${CODEX_REPO}" codex
else
  git clone --depth 1 "${CODEX_REPO}" codex
fi
cd codex

CODEX_COMMIT="$(git rev-parse HEAD)"
BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

MANIFEST_PATH="$(python3 - <<'PYCODE'
import pathlib
import sys
import tomllib

root = pathlib.Path("/work/codex-src/codex")
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
    sys.exit(1)

best = sorted(candidates, key=lambda item: (-item[0], item[1]))[0]
print(best[2])
PYCODE
)"

CARGO_TARGET_DIR="/work/codex-build/target"
mkdir -p "${CARGO_TARGET_DIR}"

BUILD_COMMAND=(
  cargo build --release
  --target "${RUST_TARGET}"
  --manifest-path "${MANIFEST_PATH}"
)

export CARGO_TARGET_DIR
export CARGO_BUILD_JOBS=1
export CARGO_PROFILE_RELEASE_LTO=off
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1
export CARGO_PROFILE_RELEASE_DEBUG=false

"${BUILD_COMMAND[@]}"

BUILT_BINARY="${CARGO_TARGET_DIR}/${RUST_TARGET}/release/codex"
if [[ ! -x "${BUILT_BINARY}" ]]; then
  echo "Built binary not found at ${BUILT_BINARY}" >&2
  exit 1
fi

OUTPUT_GZ="${OUTPUT_DIR}/${OUTPUT_BASENAME}.gz"

gzip -9 -c "${BUILT_BINARY}" > "${OUTPUT_GZ}"

cat <<README > "${OUTPUT_DIR}/README.md"
Codex glibc prebuilt binary

Repository: ${CODEX_REPO}
Tag: ${CODEX_REF:-}
Commit: ${CODEX_COMMIT}
Built at (UTC): ${BUILD_DATE}
Rust target: ${RUST_TARGET}
Cargo manifest: ${MANIFEST_PATH}
Build command: CARGO_TARGET_DIR=${CARGO_TARGET_DIR} CARGO_BUILD_JOBS=1 CARGO_PROFILE_RELEASE_LTO=off CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1 CARGO_PROFILE_RELEASE_DEBUG=false ${BUILD_COMMAND[*]}
README
