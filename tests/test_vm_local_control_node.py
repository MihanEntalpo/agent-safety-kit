from __future__ import annotations

from pathlib import Path

import yaml

from agsekit_cli.vm_local_control_node import VmLocalControlNode


PLAYBOOK = '''
- name: Prepare VM inventory
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Register Multipass VM
      ansible.builtin.add_host:
        name: "{{ vm_name }}"
        ansible_host: "{{ vm_name }}"
        ansible_connection: agsekit_multipass
        ansible_python_interpreter: /usr/bin/python3

- name: Install Qwen Code CLI
  hosts: "{{ vm_name }}"
  gather_facts: true
  tasks:
    - name: Demo task
      ansible.builtin.command: true
'''


def test_rewrite_playbook_for_local_control_node(tmp_path: Path):
    playbook = tmp_path / "qwen.yml"
    playbook.write_text(PLAYBOOK, encoding="utf-8")

    control_node = VmLocalControlNode("agent")
    control_node._rewrite_playbook_for_local_control_node(playbook)

    payload = yaml.safe_load(playbook.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert len(payload) == 1
    play = payload[0]
    assert play["hosts"] == "localhost"
    assert play["connection"] == "local"
    assert play["vars"]["ansible_python_interpreter"] == "/usr/bin/python3"
