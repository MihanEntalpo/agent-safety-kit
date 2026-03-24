from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_PREBUILT_REPO = "MihanEntalpo/agent-safety-kit"
DEFAULT_CODEX_GLIBC_PREBUILT_ASSET = "codex-glibc-linux-amd64.gz"
CODEX_GLIBC_PREBUILT_RELEASE_PREFIX = "codex-glibc-rust-v"
CODEX_GLIBC_PREBUILT_RELEASE_RE = re.compile(r"^codex-glibc-rust-v(\d+)\.(\d+)\.(\d+)$")
CODEX_GLIBC_ASSETS_BY_ARCH = {
    "x86_64": "codex-glibc-linux-amd64.gz",
    "amd64": "codex-glibc-linux-amd64.gz",
    "aarch64": "codex-glibc-linux-arm64.gz",
    "arm64": "codex-glibc-linux-arm64.gz",
}


class PrebuiltReleaseError(RuntimeError):
    """Raised when a prebuilt release cannot be resolved."""


@dataclass(frozen=True)
class PrebuiltRelease:
    repo: str
    tag: str
    asset_name: str

    @property
    def download_url(self) -> str:
        return f"https://github.com/{self.repo}/releases/download/{self.tag}/{self.asset_name}"

    def as_dict(self) -> Dict[str, str]:
        return {
            "repo": self.repo,
            "tag": self.tag,
            "asset_name": self.asset_name,
            "download_url": self.download_url,
        }


def _parse_release_version(tag: str, release_re: re.Pattern[str]) -> Optional[Tuple[int, int, int]]:
    match = release_re.fullmatch(tag)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _github_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agsekit-prebuilt-resolver",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("AGSEKIT_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_json(url: str) -> Any:
    request = Request(url, headers=_github_headers())
    try:
        with urlopen(request) as response:
            return json.load(response)
    except HTTPError as exc:
        raise PrebuiltReleaseError(f"GitHub API request failed for {url}: HTTP {exc.code}") from exc
    except URLError as exc:
        raise PrebuiltReleaseError(f"GitHub API request failed for {url}: {exc.reason}") from exc


def _asset_names(release_payload: Dict[str, Any]) -> set[str]:
    assets = release_payload.get("assets") or []
    names: set[str] = set()
    for asset in assets:
        if isinstance(asset, dict):
            name = asset.get("name")
            if isinstance(name, str) and name:
                names.add(name)
    return names


def _latest_matching_release(
    releases_payload: Iterable[Dict[str, Any]],
    asset_name: str,
    release_re: re.Pattern[str],
) -> Optional[str]:
    best: Optional[Tuple[Tuple[int, int, int], str]] = None
    for release in releases_payload:
        if not isinstance(release, dict):
            continue
        if release.get("draft"):
            continue
        tag_name = release.get("tag_name")
        if not isinstance(tag_name, str):
            continue
        version = _parse_release_version(tag_name, release_re)
        if version is None:
            continue
        if asset_name not in _asset_names(release):
            continue
        if best is None or version > best[0]:
            best = (version, tag_name)
    return best[1] if best else None


def _resolve_prebuilt_release(
    *,
    repo_env: str,
    tag_env: str,
    asset_env: str,
    default_asset: str,
    release_prefix: str,
    release_re: re.Pattern[str],
    release_kind: str,
    repo: Optional[str] = None,
    tag: Optional[str] = None,
    asset_name: Optional[str] = None,
) -> PrebuiltRelease:
    resolved_repo = (repo or os.getenv(repo_env) or DEFAULT_PREBUILT_REPO).strip()
    resolved_tag = (tag or os.getenv(tag_env) or "").strip()
    resolved_asset = (asset_name or os.getenv(asset_env) or default_asset).strip()

    if not resolved_repo:
        raise PrebuiltReleaseError("Prebuilt release repository is empty")
    if not resolved_asset:
        raise PrebuiltReleaseError("Prebuilt release asset name is empty")

    if resolved_tag:
        if _parse_release_version(resolved_tag, release_re) is None:
            raise PrebuiltReleaseError(
                "Prebuilt release tag must match "
                f"{release_prefix}<major>.<minor>.<patch>"
            )
        release_payload = _fetch_json(
            f"https://api.github.com/repos/{resolved_repo}/releases/tags/{quote(resolved_tag, safe='')}"
        )
        if resolved_asset not in _asset_names(release_payload):
            raise PrebuiltReleaseError(
                f"Release {resolved_tag} in {resolved_repo} does not contain asset {resolved_asset}"
            )
        return PrebuiltRelease(repo=resolved_repo, tag=resolved_tag, asset_name=resolved_asset)

    releases_payload = _fetch_json(f"https://api.github.com/repos/{resolved_repo}/releases?per_page=100")
    if not isinstance(releases_payload, list):
        raise PrebuiltReleaseError(f"Unexpected GitHub API response while reading releases for {resolved_repo}")

    latest_tag = _latest_matching_release(releases_payload, resolved_asset, release_re)
    if latest_tag is None:
        raise PrebuiltReleaseError(
            f"No matching {release_kind} prebuilt release found in "
            f"{resolved_repo} for asset {resolved_asset}; expected tags matching "
            f"{release_prefix}<major>.<minor>.<patch>"
        )

    return PrebuiltRelease(repo=resolved_repo, tag=latest_tag, asset_name=resolved_asset)


def codex_glibc_prebuilt_asset_for_arch(arch: str) -> str:
    normalized_arch = arch.strip().lower()
    if not normalized_arch:
        raise PrebuiltReleaseError("Architecture for codex-glibc prebuilt resolution is empty")

    asset_name = CODEX_GLIBC_ASSETS_BY_ARCH.get(normalized_arch)
    if asset_name is None:
        supported = ", ".join(sorted(CODEX_GLIBC_ASSETS_BY_ARCH))
        raise PrebuiltReleaseError(
            f"Unsupported codex-glibc prebuilt architecture {arch!r}; supported values: {supported}"
        )
    return asset_name


def resolve_codex_glibc_prebuilt_release(
    *,
    repo: Optional[str] = None,
    tag: Optional[str] = None,
    asset_name: Optional[str] = None,
    arch: Optional[str] = None,
) -> PrebuiltRelease:
    resolved_asset_name = asset_name
    if not resolved_asset_name and not os.getenv("AGSEKIT_CODEX_GLIBC_PREBUILT_ASSET") and arch:
        resolved_asset_name = codex_glibc_prebuilt_asset_for_arch(arch)

    return _resolve_prebuilt_release(
        repo_env="AGSEKIT_CODEX_GLIBC_PREBUILT_REPO",
        tag_env="AGSEKIT_CODEX_GLIBC_PREBUILT_TAG",
        asset_env="AGSEKIT_CODEX_GLIBC_PREBUILT_ASSET",
        default_asset=DEFAULT_CODEX_GLIBC_PREBUILT_ASSET,
        release_prefix=CODEX_GLIBC_PREBUILT_RELEASE_PREFIX,
        release_re=CODEX_GLIBC_PREBUILT_RELEASE_RE,
        release_kind="codex-glibc",
        repo=repo,
        tag=tag,
        asset_name=resolved_asset_name,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve agsekit prebuilt asset metadata")
    subparsers = parser.add_subparsers(dest="command", required=True)
    codex_parser = subparsers.add_parser(
        "resolve-codex-glibc-prebuilt",
        help="Print JSON metadata for the codex-glibc prebuilt release",
    )
    codex_parser.add_argument("--repo")
    codex_parser.add_argument("--tag")
    codex_parser.add_argument("--asset-name")
    codex_parser.add_argument("--arch")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "resolve-codex-glibc-prebuilt":
        try:
            release = resolve_codex_glibc_prebuilt_release(
                repo=args.repo,
                tag=args.tag,
                asset_name=args.asset_name,
                arch=args.arch,
            )
        except PrebuiltReleaseError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(release.as_dict()))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
