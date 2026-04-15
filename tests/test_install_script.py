import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = PROJECT_ROOT / "scripts" / "install" / "install.sh"


def test_install_script_is_valid_posix_sh() -> None:
    subprocess.run(["sh", "-n", str(INSTALL_SCRIPT)], check=True)


def test_wsl_multipass_symlink_is_idempotent(tmp_path: Path) -> None:
    script_body = INSTALL_SCRIPT.read_text(encoding="utf-8").replace('\nmain "$@"\n', "\n")
    fake_home = tmp_path / "home"
    fake_bin = tmp_path / "Program Files" / "Multipass" / "bin"
    fake_multipass = fake_bin / "multipass.exe"

    fake_bin.mkdir(parents=True)
    fake_home.mkdir()
    fake_multipass.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_multipass.chmod(0o755)

    driver = tmp_path / "driver.sh"
    driver.write_text(
        script_body
        + """
HOME=$1
PLATFORM=wsl
BIN_DIR="$HOME/.local/bin"
MULTIPASS_SYMLINK_PATH="$BIN_DIR/multipass"
PATH=$2:$PATH

create_or_update_wsl_multipass_symlink
""",
        encoding="utf-8",
    )

    subprocess.run(["sh", str(driver), str(fake_home), str(fake_bin)], check=True)
    subprocess.run(["sh", str(driver), str(fake_home), str(fake_bin)], check=True)

    multipass_link = fake_home / ".local" / "bin" / "multipass"
    assert multipass_link.is_symlink()
    assert multipass_link.readlink() == fake_multipass
