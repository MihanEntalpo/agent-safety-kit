from __future__ import annotations

from typing import Dict, Tuple, Type

from .aider import AiderAgent
from .base import BaseAgent, NVM_LOAD_SNIPPET
from .claude import ClaudeAgent
from .cline import ClineAgent
from .codex import CodexAgent
from .codex_glibc import CodexGlibcAgent
from .codex_glibc_prebuilt import CodexGlibcPrebuiltAgent
from .forgecode import ForgecodeAgent
from .opencode import OpencodeAgent
from .qwen import QwenAgent

AGENT_CLASSES: Tuple[Type[BaseAgent], ...] = (
    AiderAgent,
    QwenAgent,
    ForgecodeAgent,
    CodexAgent,
    OpencodeAgent,
    CodexGlibcAgent,
    CodexGlibcPrebuiltAgent,
    ClaudeAgent,
    ClineAgent,
)
AGENT_CLASS_BY_TYPE: Dict[str, Type[BaseAgent]] = {agent_cls.type_name: agent_cls for agent_cls in AGENT_CLASSES}
AGENT_CLASS_BY_RUNTIME_BINARY: Dict[str, Type[BaseAgent]] = {
    agent_cls.runtime_binary: agent_cls for agent_cls in AGENT_CLASSES
}
SUPPORTED_AGENT_TYPES: Tuple[str, ...] = tuple(AGENT_CLASS_BY_TYPE.keys())
AGENT_RUNTIME_BINARIES: Dict[str, str] = {
    agent_cls.type_name: agent_cls.runtime_binary for agent_cls in AGENT_CLASSES
}


def get_agent_class(agent_type: str) -> Type[BaseAgent]:
    return AGENT_CLASS_BY_TYPE[agent_type]


def get_agent_class_for_runtime_binary(binary: str) -> Type[BaseAgent]:
    return AGENT_CLASS_BY_RUNTIME_BINARY[binary]


def build_agent_module(agent):
    agent_cls = get_agent_class(agent.type)
    return agent_cls(agent)
