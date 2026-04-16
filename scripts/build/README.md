# Release and Build Scripts

This directory contains the release publication workflow for `agsekit`.

The main entrypoint is:

```sh
scripts/build/publish.sh prod
scripts/build/publish.sh test
```

Release development happens on `main`. Before a production release, update the
version in `pyproject.toml` and add a matching section to `changelog.md`.

## Files

- `publish.sh` is the main orchestration script. It decides whether to run the
  production workflow or the TestPyPI workflow.
- `publish-pypi.sh` creates a local build virtual environment, installs build
  tooling, cleans old artifacts, builds the package, runs `twine check`, and
  uploads artifacts to either PyPI or TestPyPI.
- `check_pypi_version.py` reads `pyproject.toml` and checks whether the same
  package version already exists on PyPI before any production tag is created.
- `extract_changelog.py` reads `pyproject.toml`, finds the exact matching
  section in `changelog.md`, and extracts release notes.
- `create-github-release.sh` creates a GitHub Release from an already pushed
  tag using `gh release create --verify-tag`.
- `backfill-github-releases.sh` is a one-shot helper for filling missing
  GitHub Releases for versions that already exist on PyPI.
- `backfill_github_releases.py` contains the implementation used by the
  backfill shell entrypoint.
- `README.md` documents the subsystem.

## Why These Scripts Exist

The release process has several states that must stay aligned:

- `pyproject.toml` version
- git tag
- PyPI package version
- GitHub Release tag
- changelog section

The scripts keep those states tied to the same version and deliberately split
responsibilities so each step is easy to inspect. The PyPI helper only builds
and uploads Python artifacts. The GitHub helper only creates a release from a
tag that already exists on the remote. The main script owns ordering and safety
checks.

## Prerequisites

- Run production releases from branch `main`.
- Keep the git working tree clean before `prod`.
- Ensure `pyproject.toml` contains the intended release version.
- Ensure `changelog.md` contains a section with exactly that version.
- Python 3.9+ must be available as `python3`, or set `PYTHON` for
  `publish-pypi.sh`.
- PyPI/TestPyPI credentials must be configured for `twine`.
- Production releases need network access to `pypi.org` for the preflight
  version-existence check.
- `gh` must be installed and authenticated before creating a GitHub Release.
- The repository remote must be named `origin`.

`extract_changelog.py` and `check_pypi_version.py` use stdlib `tomllib` on
Python 3.11+. On Python 3.9 or 3.10 they fall back to `tomli`.

## Production Workflow

Run:

```sh
scripts/build/publish.sh prod
```

The production workflow does this:

1. Verifies that the git working tree is clean.
2. Verifies that the current branch is `main`.
3. Reads `project.version` from `pyproject.toml`.
4. Checks that PyPI does not already contain this package version.
5. Extracts the matching release notes from `changelog.md`.
6. Creates a local annotated tag named `v<version>`, or reuses an existing
   local tag only when it points to the current commit and does not exist on
   `origin`.
7. Builds package artifacts.
8. Runs `twine check`.
9. Uploads to real PyPI.
10. Only after a successful PyPI upload, pushes `main`.
11. Pushes the tag.
12. Creates the GitHub Release using the pushed tag and changelog notes.

If the workflow fails before the PyPI upload succeeds, the local tag created by
the script is removed. If the PyPI upload succeeds but a later push or GitHub
step fails, the local tag is kept so the release can be repaired without
changing the version.

If a previous run failed after creating the local tag but before pushing it, a
retry can continue from that local tag. The retry is allowed only when the tag
points to the current `HEAD` and the same tag is still absent from `origin`.

## TestPyPI Workflow

Run:

```sh
scripts/build/publish.sh test
```

The test workflow does only this:

1. Builds package artifacts.
2. Runs `twine check`.
3. Uploads to TestPyPI.

It does not create tags, push commits, push tags, or create GitHub Releases.

## Direct Helper Usage

The helpers can be run directly when debugging a release step:

```sh
scripts/build/publish-pypi.sh test
scripts/build/publish-pypi.sh prod
python3 scripts/build/check_pypi_version.py --repository pypi
python3 scripts/build/extract_changelog.py
python3 scripts/build/extract_changelog.py --version-only
scripts/build/create-github-release.sh v1.2.3 /tmp/release-notes.md
scripts/build/backfill-github-releases.sh
scripts/build/backfill-github-releases.sh --apply
scripts/build/backfill-github-releases.sh --version 1.2.3 --apply
```

Normally, use `publish.sh` instead of calling helpers manually.

The repository-root `publish.sh` is kept as a convenience wrapper and delegates
to `scripts/build/publish.sh`.

## GitHub Release Backfill

`backfill-github-releases.sh` is intended as a one-time maintenance script for
projects that already have package versions on PyPI but do not yet have matching
GitHub Releases.

The default mode is dry-run:

```sh
scripts/build/backfill-github-releases.sh
```

Real changes require `--apply`:

```sh
scripts/build/backfill-github-releases.sh --apply
```

The script does this for each changelog section:

1. Checks whether that version exists on PyPI.
2. Skips the version when PyPI does not contain it.
3. Finds the first commit in `pyproject.toml` history where that exact version
   appeared.
4. Checks whether `v<version>` exists on `origin`.
5. If the tag exists, verifies that it points to the expected commit.
6. If the tag is missing, creates an annotated tag at that commit and pushes it
   when `--apply` is used.
7. Checks whether a GitHub Release for that tag already exists.
8. If the release is missing, creates it with changelog notes when `--apply` is
   used.

For safety, `--apply` requires a clean working tree and branch `main`. The
script never rewrites existing remote tags and never edits existing GitHub
Releases. If a remote tag points to a different commit than the one where the
version first appeared in `pyproject.toml`, the script reports an error and
skips that version.

You can limit a run to specific versions:

```sh
scripts/build/backfill-github-releases.sh --version 1.5.13
scripts/build/backfill-github-releases.sh --version 1.5.13 --version 1.5.12 --apply
```

## Changelog Parsing

The parser expects the current changelog format:

```md
## 1.2.4 - Addmount VM selection

* Improved `addmount`: VM can now be chosen explicitly via `--vm`
```

It finds the section whose version exactly matches `project.version` from
`pyproject.toml`. It does not assume that the first section is the latest
release. It fails if the matching section is missing, duplicated, or empty.

GitHub Release notes include only the body of the matching changelog section,
not the `## <version> - <title>` header. The GitHub Release title is the tag
itself, so excluding the markdown header avoids duplicated release titles.

The repository currently stores this file as `changelog.md`. The parser also
accepts `CHANGELOG.md` if that file exists, and `--changelog <path>` can be used
for explicit testing.

## Ordering Rationale

The production flow checks PyPI before creating or verifying a local tag. This
prevents the script from creating a local tag for a version that has already
been published. After that, the script creates or verifies a local tag before
building so the release identity is fixed early. It does not push that tag until
after PyPI upload succeeds. This protects the public repository from a tag that
points to a release version that never reached PyPI.

The GitHub Release is created last and uses `gh release create --verify-tag`.
That means the release can only be created from a tag that already exists on the
remote. Release notes come from `changelog.md` through `--notes-file`; generated
GitHub notes are intentionally not used.
