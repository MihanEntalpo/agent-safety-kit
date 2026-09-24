from __future__ import annotations

from types import SimpleNamespace

import pytest

from agsekit_cli import agent_version_sources
from agsekit_cli.agents_modules.aider import AiderAgent
from agsekit_cli.agents_modules.claude import ClaudeAgent
from agsekit_cli.agents_modules.cline import ClineAgent
from agsekit_cli.agents_modules.codex import CodexAgent
from agsekit_cli.agents_modules.codex_glibc import CodexGlibcAgent
from agsekit_cli.agents_modules.codex_glibc_prebuilt import CodexGlibcPrebuiltAgent
from agsekit_cli.agents_modules.forgecode import ForgecodeAgent
from agsekit_cli.agents_modules.opencode import OpencodeAgent
from agsekit_cli.agents_modules.qwen import QwenAgent


@pytest.mark.parametrize(
    ("agent_class", "module_name", "function_name", "package_name"),
    [
        (AiderAgent, "agsekit_cli.agents_modules.aider", "latest_pypi_version", "aider-chat"),
        (CodexAgent, "agsekit_cli.agents_modules.codex", "latest_npm_version", "@openai/codex"),
        (QwenAgent, "agsekit_cli.agents_modules.qwen", "latest_npm_version", "@qwen-code/qwen-code"),
        (OpencodeAgent, "agsekit_cli.agents_modules.opencode", "latest_npm_version", "opencode-ai"),
        (ClaudeAgent, "agsekit_cli.agents_modules.claude", "latest_npm_version", "@anthropic-ai/claude-code"),
        (ClineAgent, "agsekit_cli.agents_modules.cline", "latest_npm_version", "cline"),
    ],
)
def test_registry_agent_classes_check_their_own_latest_version(
    monkeypatch, agent_class, module_name, function_name, package_name
):
    calls = []

    def fake_lookup(name, *, timeout):
        calls.append((name, timeout))
        return "v1.2.3"

    monkeypatch.setattr(f"{module_name}.{function_name}", fake_lookup)

    assert agent_class.check_latest_version(architecture="x86_64", timeout=12.0) == "1.2.3"
    assert calls == [(package_name, 12.0)]


@pytest.mark.parametrize(
    ("agent_class", "module_name", "repo", "prefix"),
    [
        (ForgecodeAgent, "agsekit_cli.agents_modules.forgecode", "tailcallhq/forgecode", "v"),
        (CodexGlibcAgent, "agsekit_cli.agents_modules.codex_glibc", "openai/codex", "rust-v"),
    ],
)
def test_github_agent_classes_check_their_own_latest_version(
    monkeypatch, agent_class, module_name, repo, prefix
):
    calls = []

    def fake_lookup(name, *, tag_prefix, timeout):
        calls.append((name, tag_prefix, timeout))
        return "1.2.3"

    monkeypatch.setattr(f"{module_name}.latest_github_release_version", fake_lookup)

    assert agent_class.check_latest_version(architecture="x86_64", timeout=8.0) == "1.2.3"
    assert calls == [(repo, prefix, 8.0)]


def test_prebuilt_latest_version_uses_current_architecture(monkeypatch):
    calls = []

    def fake_resolve(*, arch):
        calls.append(arch)
        return SimpleNamespace(tag="codex-glibc-rust-v0.155.1")

    monkeypatch.setattr(
        "agsekit_cli.agents_modules.codex_glibc_prebuilt.resolve_codex_glibc_prebuilt_release",
        fake_resolve,
    )

    assert CodexGlibcPrebuiltAgent.check_latest_version(architecture="x86_64") == "0.155.1"
    assert calls == ["x86_64"]


def test_latest_github_release_version_chooses_highest_stable_version(monkeypatch):
    monkeypatch.setattr(
        agent_version_sources,
        "fetch_json",
        lambda *_args, **_kwargs: [
            {"tag_name": "v1.3.0-beta.1", "prerelease": True},
            {"tag_name": "v1.2.0"},
            {"tag_name": "v1.10.0"},
            {"tag_name": "other-9.0.0"},
        ],
    )

    assert agent_version_sources.latest_github_release_version("owner/repo", tag_prefix="v") == "1.10.0"
