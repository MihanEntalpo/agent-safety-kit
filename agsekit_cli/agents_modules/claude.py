from .base import BaseAgent


class ClaudeAgent(BaseAgent):
    type_name = "claude"
    runtime_binary = "claude"
    default_version = "2.1.141"
    default_env = {"DISABLE_AUTOUPDATER": "1"}
    _needs_nvm = True
