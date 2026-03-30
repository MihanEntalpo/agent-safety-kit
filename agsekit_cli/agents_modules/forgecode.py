from typing import Dict

from .base import BaseAgent


class ForgecodeAgent(BaseAgent):
    type_name = "forgecode"
    runtime_binary = "forge"

    def build_env(self) -> Dict[str, str]:
        env = dict(self.agent.env)
        env["FORGE_TRACKER"] = "false"
        return env
