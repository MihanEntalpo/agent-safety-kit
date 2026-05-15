from .base import BaseAgent


class ForgecodeAgent(BaseAgent):
    type_name = "forgecode"
    runtime_binary = "forge"
    default_version = "2.12.14"
    default_env = {"FORGE_TRACKER": "false"}
