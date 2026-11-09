from typing import List

from .base import BaseAgent


class CustomAgent(BaseAgent):
    type_name = "custom"
    runtime_binary = ""
    installable = False
    tracks_latest_version = False
    supports_version = False

    def command_prefix(self) -> List[str]:
        return list(self.agent.command or [])
