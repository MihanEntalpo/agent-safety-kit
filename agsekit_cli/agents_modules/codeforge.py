from typing import Dict

from .base import BaseAgent


class CodeforgeAgent(BaseAgent):
    type_name = "codeforge"
    runtime_binary = "forge"

    def build_env(self) -> Dict[str, str]:
        env = dict(self.agent.env)
        env["FORGE_TRACKER"] = "false"
        return env
