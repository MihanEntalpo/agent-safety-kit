#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat >&2 <<'EOF'
Usage: scripts/build/publish.sh {prod|test}

prod: tag, build, upload to PyPI, push main/tag, create GitHub Release
test: build and upload to TestPyPI only
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

ensure_clean_worktree() {
    if [ -n "$(git status --porcelain)" ]; then
        die "Git working tree is not clean. Commit or stash changes before a production release."
    fi
}

ensure_main_branch() {
    local branch
    branch=$(git branch --show-current)
    if [ "$branch" != "main" ]; then
        die "Production releases must be made from main; current branch is $branch."
    fi
}

remote_tag_exists() {
    local tag=$1

    local output
    set +e
    output=$(git ls-remote --exit-code --tags origin "refs/tags/$tag" 2>&1)
    local status=$?
    set -e

    case "$status" in
        0)
            return 0
            ;;
        2)
            return 1
            ;;
        *)
            die "Could not check remote tag $tag on origin: $output"
            ;;
    esac
}

local_tag_exists() {
    local tag=$1
    git rev-parse --quiet --verify "refs/tags/$tag" >/dev/null
}

ensure_local_tag_points_to_head() {
    local tag=$1
    local tag_commit
    local head_commit

    tag_commit=$(git rev-parse --verify "$tag^{commit}") || die "Could not resolve local tag $tag to a commit."
    head_commit=$(git rev-parse --verify HEAD)

    if [ "$tag_commit" != "$head_commit" ]; then
        die "Local tag $tag exists but points to $tag_commit, while HEAD is $head_commit."
    fi
}

cleanup_on_exit() {
    local status=$?
    if [ "$status" -ne 0 ] && [ "${TAG_CREATED:-0}" -eq 1 ] && [ "${PYPI_UPLOAD_SUCCEEDED:-0}" -eq 0 ]; then
        printf 'Removing local tag %s because the release failed before PyPI upload succeeded.\n' "$TAG" >&2
        git tag -d "$TAG" >/dev/null 2>&1 || true
    fi
    if [ -n "${NOTES_FILE:-}" ] && [ -f "$NOTES_FILE" ]; then
        rm -f "$NOTES_FILE"
    fi
}

ensure_release_tag_ready() {
    local tag=$1

    if remote_tag_exists "$tag"; then
        die "Tag already exists on origin: $tag"
    fi

    if local_tag_exists "$tag"; then
        ensure_local_tag_points_to_head "$tag"
        printf 'Reusing local tag %s because it points to HEAD and is not present on origin.\n' "$tag"
        TAG_CREATED=0
        return 0
    fi

    printf 'Creating local annotated tag %s...\n' "$tag"
    git tag -a "$tag" -m "Release $tag"
    TAG_CREATED=1
}

run_prod() {
    require_command git
    require_command python3

    ensure_clean_worktree
    ensure_main_branch

    VERSION=$(python3 "$SCRIPT_DIR/extract_changelog.py" --version-only)
    printf 'Checking PyPI for existing version %s...\n' "$VERSION"
    python3 "$SCRIPT_DIR/check_pypi_version.py" --repository pypi --version "$VERSION"

    TAG="v$VERSION"
    NOTES_FILE=$(mktemp "${TMPDIR:-/tmp}/agsekit-release-notes.XXXXXX.md")
    TAG_CREATED=0
    PYPI_UPLOAD_SUCCEEDED=0
    trap cleanup_on_exit EXIT

    printf 'Validating changelog section for %s...\n' "$VERSION"
    python3 "$SCRIPT_DIR/extract_changelog.py" --version "$VERSION" --output "$NOTES_FILE"

    ensure_release_tag_ready "$TAG"

    "$SCRIPT_DIR/publish-pypi.sh" prod
    PYPI_UPLOAD_SUCCEEDED=1

    printf 'Pushing main...\n'
    git push origin main

    printf 'Pushing tag %s...\n' "$TAG"
    git push origin "$TAG"

    "$SCRIPT_DIR/create-github-release.sh" "$TAG" "$NOTES_FILE"

    printf 'Production release %s completed.\n' "$TAG"
}

run_test() {
    "$SCRIPT_DIR/publish-pypi.sh" test
}

if [ "$#" -ne 1 ]; then
    usage
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

case "$1" in
    prod)
        run_prod
        ;;
    test)
        run_test
        ;;
    *)
        usage
        ;;
esac
