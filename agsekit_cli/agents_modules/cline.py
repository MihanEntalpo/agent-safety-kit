from .base import BaseAgent


class ClineAgent(BaseAgent):
    type_name = "cline"
    runtime_binary = "cline"
    default_version = "2.17.0"
    default_env = {"CLINE_NO_AUTO_UPDATE": "1"}
    _needs_nvm = True
