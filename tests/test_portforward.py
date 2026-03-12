from agsekit_cli.commands import portforward as portforward_module
from agsekit_cli.config import PortForwardingRule


def test_find_privileged_remote_ports():
    rules = [
        PortForwardingRule(type="local", host_addr="127.0.0.1:8080", vm_addr="127.0.0.1:80"),
        PortForwardingRule(type="remote", host_addr="127.0.0.1:8080", vm_addr="127.0.0.1:80"),
        PortForwardingRule(type="remote", host_addr="127.0.0.1:8081", vm_addr="127.0.0.1:443"),
        PortForwardingRule(type="remote", host_addr="127.0.0.1:8082", vm_addr="127.0.0.1:8082"),
    ]

    ports = portforward_module._find_privileged_remote_ports(rules)

    assert ports == [80, 443]
