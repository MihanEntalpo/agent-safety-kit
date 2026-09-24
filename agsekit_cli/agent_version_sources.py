from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version


class AgentVersionCheckError(RuntimeError):
    """Raised when an upstream agent version cannot be resolved."""


def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/json", "User-Agent": "agsekit-agent-version-check"}
    token = os.getenv("AGSEKIT_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_json(url: str, *, timeout: float = 30.0) -> Any:
    request = Request(url, headers=_headers())
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        raise AgentVersionCheckError(f"Version request failed for {url}: HTTP {exc.code}") from exc
    except URLError as exc:
        raise AgentVersionCheckError(f"Version request failed for {url}: {exc.reason}") from exc
    except (OSError, ValueError) as exc:
        raise AgentVersionCheckError(f"Invalid version response from {url}: {exc}") from exc


def latest_npm_version(package_name: str, *, timeout: float = 30.0) -> str:
    payload = fetch_json(
        f"https://registry.npmjs.org/{quote(package_name, safe='')}/latest",
        timeout=timeout,
    )
    version = payload.get("version") if isinstance(payload, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise AgentVersionCheckError(f"npm did not report a latest version for {package_name}")
    return version.strip()


def latest_pypi_version(package_name: str, *, timeout: float = 30.0) -> str:
    payload = fetch_json(f"https://pypi.org/pypi/{quote(package_name, safe='')}/json", timeout=timeout)
    info = payload.get("info") if isinstance(payload, dict) else None
    version = info.get("version") if isinstance(info, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise AgentVersionCheckError(f"PyPI did not report a latest version for {package_name}")
    return version.strip()


def _stable_versions(values: Iterable[str]) -> Iterable[Version]:
    for value in values:
        try:
            parsed = Version(value)
        except InvalidVersion:
            continue
        if not parsed.is_prerelease and not parsed.is_devrelease:
            yield parsed


def latest_github_release_version(
    repo: str,
    *,
    tag_prefix: str,
    timeout: float = 30.0,
) -> str:
    payload = fetch_json(f"https://api.github.com/repos/{repo}/releases?per_page=100", timeout=timeout)
    if not isinstance(payload, list):
        raise AgentVersionCheckError(f"GitHub did not report releases for {repo}")

    candidates = []
    for release in payload:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        tag = release.get("tag_name")
        if not isinstance(tag, str) or not tag.startswith(tag_prefix):
            continue
        candidates.append(tag[len(tag_prefix):])

    versions = list(_stable_versions(candidates))
    if not versions:
        raise AgentVersionCheckError(f"GitHub did not report a stable {tag_prefix} release for {repo}")
    return str(max(versions))
