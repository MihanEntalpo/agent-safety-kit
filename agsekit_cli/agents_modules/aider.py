from .base import BaseAgent


class AiderAgent(BaseAgent):
    type_name = "aider"
    runtime_binary = "aider"
    default_version = "0.86.2"
    default_env = {"AIDER_CHECK_UPDATE": "false"}
