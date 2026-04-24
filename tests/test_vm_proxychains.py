from __future__ import annotations

from typing import Optional

import agsekit_cli.vm as vm_module
from agsekit_cli.config import VmConfig


def _vm(name: str = "agent-vm", proxychains: Optional[str] = "socks5://127.0.0.1:1080") -> VmConfig:
    return VmConfig(name=name, cpu=1, ram="1G", disk="5G", cloud_init={}, port_forwarding=[], proxychains=proxychains)


def test_proxychains_runner_path_is_global_script() -> None:
    assert vm_module.PROXYCHAINS_RUNNER_PATH == "/usr/bin/agsekit-run_with_proxychains.sh"


def test_http_proxy_runner_path_is_global_script() -> None:
    assert vm_module.HTTP_PROXY_RUNNER_PATH == "/usr/bin/agsekit-run_with_http_proxy.sh"

def test_run_agent_runner_path_is_global_script() -> None:
    assert vm_module.RUN_AGENT_RUNNER_PATH == "/usr/bin/agsekit-run_agent.sh"


def test_resolve_proxychains_uses_vm_value_by_default() -> None:
    vm = _vm(proxychains="socks5://127.0.0.1:1080")
    assert vm_module.resolve_proxychains(vm, None) == "socks5://127.0.0.1:1080"


def test_resolve_proxychains_empty_override_disables_proxychains() -> None:
    vm = _vm(proxychains="socks5://127.0.0.1:1080")
    assert vm_module.resolve_proxychains(vm, "") is None
