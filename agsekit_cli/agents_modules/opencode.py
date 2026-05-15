from .base import BaseAgent


class OpencodeAgent(BaseAgent):
    type_name = "opencode"
    runtime_binary = "opencode"
    default_version = "1.14.50"
    default_env = {"OPENCODE_DISABLE_AUTOUPDATE": "true"}
    _needs_nvm = True
