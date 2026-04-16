#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat >&2 <<'EOF'
Usage: scripts/build/create-github-release.sh <tag> <notes-file>

Create a GitHub Release for an already pushed tag using notes from a file.
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

if [ "$#" -ne 2 ]; then
    usage
fi

TAG=$1
NOTES_FILE=$2

case "$TAG" in
    v*) ;;
    *) die "Tag must use the v<version> format; got: $TAG" ;;
esac

[ -f "$NOTES_FILE" ] || die "Release notes file does not exist: $NOTES_FILE"
[ -s "$NOTES_FILE" ] || die "Release notes file is empty: $NOTES_FILE"

require_command git
require_command gh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

if ! git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null 2>&1; then
    die "Tag $TAG is not present on origin. Push the tag before creating the GitHub Release."
fi

printf 'Creating GitHub Release for %s...\n' "$TAG"
gh release create "$TAG" \
    --verify-tag \
    --title "$TAG" \
    --notes-file "$NOTES_FILE"
