from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = PROJECT_ROOT / "scripts" / "install" / "install.sh"
WINDOWS_INSTALL_SCRIPT = PROJECT_ROOT / "scripts" / "install" / "install.ps1"


def test_posix_install_script_exists() -> None:
    assert INSTALL_SCRIPT.is_file()


def test_windows_install_script_exists() -> None:
    assert WINDOWS_INSTALL_SCRIPT.is_file()
