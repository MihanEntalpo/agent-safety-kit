from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_docker_bundle_uses_fact_free_user_for_group_membership():
    playbook = _load_yaml(Path("agsekit_cli/ansible/bundles/docker.yml"))
    install_play = playbook[1]
    tasks = install_play["tasks"]

    membership_task = next(item for item in tasks if item["name"] == "Ensure docker group membership")
    user_args = membership_task["ansible.builtin.user"]

    assert install_play["gather_facts"] is False
    assert user_args["name"] == "{{ ansible_user | default('ubuntu') }}"


def test_pyenv_bundle_checks_installation_via_pyenv_root_marker():
    playbook = _load_yaml(Path("agsekit_cli/ansible/bundles/pyenv.yml"))
    install_play = playbook[1]
    tasks = install_play["tasks"]

    check_task = next(item for item in tasks if item["name"] == "Check for pyenv executable")
    assert check_task["ansible.builtin.stat"]["path"] == "{{ pyenv_root }}/bin/pyenv"

    deps_task = next(item for item in tasks if item["name"] == "Install pyenv dependencies")
    install_task = next(item for item in tasks if item["name"] == "Install pyenv")
    assert deps_task["when"] == "not pyenv_stat.stat.exists"
    assert install_task["when"] == "not pyenv_stat.stat.exists"


def test_python_bundle_does_not_require_pyenv_in_shell_path():
    playbook = _load_yaml(Path("agsekit_cli/ansible/bundles/python.yml"))
    install_play = playbook[1]
    tasks = install_play["tasks"]

    check_task = next(item for item in tasks if item["name"] == "Ensure pyenv is installed")
    assert check_task["ansible.builtin.stat"]["path"] == "{{ pyenv_root }}/bin/pyenv"

    fail_task = next(item for item in tasks if item["name"] == "Fail when pyenv is missing")
    assert fail_task["when"] == "not pyenv_stat.stat.exists"
