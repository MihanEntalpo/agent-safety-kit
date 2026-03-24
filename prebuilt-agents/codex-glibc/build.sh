#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/builds"
IMAGE_NAME="agsekit-codex-glibc-builder"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "${BUILD_DIR}"

echo "[build.sh] Using build directory: ${BUILD_DIR}"
echo "[build.sh] Docker image name: ${IMAGE_NAME}"
echo "[build.sh] DRY_RUN: ${DRY_RUN}"

if [[ -z "${CODEX_REF:-}" ]]; then
  echo "[build.sh] Resolving latest rust-v* tag from https://github.com/openai/codex.git"
  version_tags="$(
    git ls-remote --tags --refs https://github.com/openai/codex.git \
      | awk '{print $2}' \
      | tr -d '\r' \
      | { grep -E '^refs/tags/rust-v[0-9]+\.[0-9]+\.[0-9]+$' || true; } \
      | sed 's#refs/tags/##' \
      | sort -u
  )"
  candidate_count="$(printf '%s\n' "${version_tags}" | sed '/^$/d' | wc -l | tr -d ' ')"
  echo "[build.sh] Found ${candidate_count} rust-v* release tags"
  latest_version="$(printf '%s\n' "${version_tags}" | sort -V | tail -n1)"
  if [[ -n "${latest_version}" ]]; then
    CODEX_REF="${latest_version}"
  fi
  if [[ -z "${CODEX_REF:-}" ]]; then
    echo "Failed to resolve latest rust-v* tag from https://github.com/openai/codex.git" >&2
    echo "Note: this resolver only accepts release tags matching ^rust-v<major>.<minor>.<patch>$" >&2
    echo "Sample tags from ls-remote:" >&2
    git ls-remote --tags --refs https://github.com/openai/codex.git | awk '{print $2}' | head -n 20 >&2
    exit 1
  fi
fi

echo "[build.sh] Using CODEX_REPO: ${CODEX_REPO:-https://github.com/openai/codex.git}"
echo "[build.sh] Using CODEX_REF: ${CODEX_REF}"
echo "[build.sh] Using RUST_TARGET: ${RUST_TARGET:-x86_64-unknown-linux-gnu}"
echo "[build.sh] Using OUTPUT_BASENAME: ${OUTPUT_BASENAME:-codex-glibc-linux-amd64}"
echo "[build.sh] Using OUTPUT_INFO_NAME: ${OUTPUT_INFO_NAME:-${OUTPUT_BASENAME:-codex-glibc-linux-amd64}-info.txt}"

echo "[build.sh] Building Docker image..."
if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[build.sh] DRY_RUN: docker build -t \"${IMAGE_NAME}\" -f \"${SCRIPT_DIR}/Dockerfile\" \"${SCRIPT_DIR}\""
else
  docker build -t "${IMAGE_NAME}" -f "${SCRIPT_DIR}/Dockerfile" "${SCRIPT_DIR}"
fi

echo "[build.sh] Running build container..."
if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[build.sh] DRY_RUN: docker run --rm \\"
  echo "[build.sh]   --user \"$(id -u):$(id -g)\" \\"
  echo "[build.sh]   -e CODEX_REPO=\"${CODEX_REPO:-https://github.com/openai/codex.git}\" \\"
  echo "[build.sh]   -e CODEX_REF=\"${CODEX_REF}\" \\"
  echo "[build.sh]   -e RUST_TARGET=\"${RUST_TARGET:-x86_64-unknown-linux-gnu}\" \\"
  echo "[build.sh]   -e OUTPUT_BASENAME=\"${OUTPUT_BASENAME:-codex-glibc-linux-amd64}\" \\"
  echo "[build.sh]   -e OUTPUT_INFO_NAME=\"${OUTPUT_INFO_NAME:-${OUTPUT_BASENAME:-codex-glibc-linux-amd64}-info.txt}\" \\"
  echo "[build.sh]   -e OUTPUT_DIR=/out \\"
  echo "[build.sh]   -v \"${BUILD_DIR}:/out\" \\"
  echo "[build.sh]   \"${IMAGE_NAME}\""
else
  docker run --rm \
    --user "$(id -u):$(id -g)" \
    -e CODEX_REPO="${CODEX_REPO:-https://github.com/openai/codex.git}" \
    -e CODEX_REF="${CODEX_REF}" \
    -e RUST_TARGET="${RUST_TARGET:-x86_64-unknown-linux-gnu}" \
    -e OUTPUT_BASENAME="${OUTPUT_BASENAME:-codex-glibc-linux-amd64}" \
    -e OUTPUT_INFO_NAME="${OUTPUT_INFO_NAME:-${OUTPUT_BASENAME:-codex-glibc-linux-amd64}-info.txt}" \
    -e OUTPUT_DIR=/out \
    -v "${BUILD_DIR}:/out" \
    "${IMAGE_NAME}"
fi

if [[ "${DRY_RUN}" != "1" ]]; then
  echo "[build.sh] Build completed. Outputs:"
  ls -lah "${BUILD_DIR}"
fi
