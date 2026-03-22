from __future__ import annotations

import json

import pytest

from agsekit_cli.prebuilt import (
    PrebuiltReleaseError,
    resolve_codex_glibc_prebuilt_release,
)


def test_resolve_codex_glibc_prebuilt_release_selects_latest_matching_release(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {
            "tag_name": "v1.4.2",
            "draft": False,
            "assets": [{"name": "codex-glibc-linux-amd64.gz"}],
        },
        {
            "tag_name": "codex-glibc-rust-v0.114.0",
            "draft": False,
            "assets": [{"name": "codex-glibc-linux-amd64.gz"}],
        },
        {
            "tag_name": "codex-glibc-rust-v0.115.0",
            "draft": False,
            "assets": [{"name": "README.md"}],
        },
        {
            "tag_name": "codex-glibc-rust-v0.113.0",
            "draft": False,
            "assets": [{"name": "codex-glibc-linux-amd64.gz"}],
        },
    ]

    monkeypatch.setattr("agsekit_cli.prebuilt._fetch_json", lambda url: payload)

    release = resolve_codex_glibc_prebuilt_release(repo="example/repo")

    assert release.repo == "example/repo"
    assert release.tag == "codex-glibc-rust-v0.114.0"
    assert release.asset_name == "codex-glibc-linux-amd64.gz"
    assert (
        release.download_url
        == "https://github.com/example/repo/releases/download/codex-glibc-rust-v0.114.0/codex-glibc-linux-amd64.gz"
    )


def test_resolve_codex_glibc_prebuilt_release_validates_explicit_tag_asset(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_fetch(url: str) -> object:
        return {
            "tag_name": "codex-glibc-rust-v0.114.0",
            "draft": False,
            "assets": [{"name": "codex-glibc-linux-amd64.gz"}],
        }

    monkeypatch.setattr("agsekit_cli.prebuilt._fetch_json", fake_fetch)

    release = resolve_codex_glibc_prebuilt_release(
        repo="example/repo",
        tag="codex-glibc-rust-v0.114.0",
    )

    assert json.loads(json.dumps(release.as_dict()))["tag"] == "codex-glibc-rust-v0.114.0"


def test_resolve_codex_glibc_prebuilt_release_rejects_bad_tag() -> None:
    with pytest.raises(PrebuiltReleaseError, match="must match"):
        resolve_codex_glibc_prebuilt_release(repo="example/repo", tag="rust-v0.114.0")
