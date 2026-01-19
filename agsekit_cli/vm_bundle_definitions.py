from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

INSTALLERS_DIR = Path(__file__).resolve().parent / "vm_installers"


@dataclass(frozen=True)
class BundleDefinition:
    name: str
    description: str
    script: Path
    dependencies: tuple[str, ...] = ()
    supports_version: bool = False


BUNDLE_DEFINITIONS: dict[str, BundleDefinition] = {
    "pyenv": BundleDefinition(
        name="pyenv",
        description="Install pyenv and Python build dependencies.",
        script=INSTALLERS_DIR / "pyenv.sh",
    ),
    "nvm": BundleDefinition(
        name="nvm",
        description="Install nvm and shell initialization hooks.",
        script=INSTALLERS_DIR / "nvm.sh",
    ),
    "python": BundleDefinition(
        name="python",
        description="Install pyenv and a requested Python version.",
        script=INSTALLERS_DIR / "python.sh",
        dependencies=("pyenv",),
        supports_version=True,
    ),
    "nodejs": BundleDefinition(
        name="nodejs",
        description="Install nvm and a requested Node.js version.",
        script=INSTALLERS_DIR / "nodejs.sh",
        dependencies=("nvm",),
        supports_version=True,
    ),
    "rust": BundleDefinition(
        name="rust",
        description="Install rustup and the Rust toolchain.",
        script=INSTALLERS_DIR / "rust.sh",
    ),
    "golang": BundleDefinition(
        name="golang",
        description="Install the Go toolchain via apt.",
        script=INSTALLERS_DIR / "golang.sh",
    ),
    "docker": BundleDefinition(
        name="docker",
        description="Install Docker Engine and Docker Compose via Docker's apt repo.",
        script=INSTALLERS_DIR / "docker.sh",
    ),
}
