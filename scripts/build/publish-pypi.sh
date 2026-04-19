#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat >&2 <<'EOF'
Usage: scripts/build/publish-pypi.sh {prod|test}

Build artifacts, run twine check, and upload to PyPI or TestPyPI.
EOF
    exit 2
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "$1 is required."
}

if [ "$#" -ne 1 ]; then
    usage
fi

case "$1" in
    prod)
        REPOSITORY="pypi"
        ;;
    test)
        REPOSITORY="testpypi"
        ;;
    *)
        usage
        ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="${PYTHON:-python3}"

require_command "$PYTHON_BIN"

if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR" || die "Could not create build venv at $VENV_DIR."
fi

VENV_PYTHON="$VENV_DIR/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
    die "Build venv Python was not found at $VENV_PYTHON."
fi

printf 'Preparing build tooling in %s\n' "$VENV_DIR"
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install --upgrade build twine

printf 'Cleaning old build artifacts...\n'
rm -rf "$PROJECT_ROOT/dist" "$PROJECT_ROOT/build"
find "$PROJECT_ROOT" -maxdepth 1 -name '*.egg-info' -exec rm -rf {} +

cd "$PROJECT_ROOT"

printf 'Building package artifacts...\n'
"$VENV_PYTHON" -m build

artifacts=(dist/*)
if [ ! -e "${artifacts[0]}" ]; then
    die "No artifacts were produced in dist/."
fi

printf 'Running twine check...\n'
"$VENV_PYTHON" -m twine check "${artifacts[@]}"

printf 'Uploading to repository: %s\n' "$REPOSITORY"
"$VENV_PYTHON" -m twine upload --repository "$REPOSITORY" "${artifacts[@]}"
