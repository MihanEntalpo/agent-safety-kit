from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ANSIBLE_BUNDLES_DIR = Path(__file__).resolve().parent / "ansible" / "bundles"


@dataclass(frozen=True)
class BundleDefinition:
    name: str
    description: str
    playbook: Path
    dependencies: tuple[str, ...] = ()
    supports_version: bool = False


BUNDLE_DEFINITIONS: dict[str, BundleDefinition] = {
    "pyenv": BundleDefinition(
        name="pyenv",
        description="Install pyenv and Python build dependencies.",
        playbook=ANSIBLE_BUNDLES_DIR / "pyenv.yml",
    ),
    "nvm": BundleDefinition(
        name="nvm",
        description="Install nvm and shell initialization hooks.",
        playbook=ANSIBLE_BUNDLES_DIR / "nvm.yml",
    ),
    "python": BundleDefinition(
        name="python",
        description="Install pyenv and a requested Python version.",
        playbook=ANSIBLE_BUNDLES_DIR / "python.yml",
        dependencies=("pyenv",),
        supports_version=True,
    ),
    "nodejs": BundleDefinition(
        name="nodejs",
        description="Install nvm and a requested Node.js version.",
        playbook=ANSIBLE_BUNDLES_DIR / "nodejs.yml",
        dependencies=("nvm",),
        supports_version=True,
    ),
    "rust": BundleDefinition(
        name="rust",
        description="Install rustup and the Rust toolchain.",
        playbook=ANSIBLE_BUNDLES_DIR / "rust.yml",
    ),
    "golang": BundleDefinition(
        name="golang",
        description="Install the Go toolchain via apt.",
        playbook=ANSIBLE_BUNDLES_DIR / "golang.yml",
    ),
    "docker": BundleDefinition(
        name="docker",
        description="Install Docker Engine and Docker Compose via Docker's apt repo.",
        playbook=ANSIBLE_BUNDLES_DIR / "docker.yml",
    ),
}
