import subprocess
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = PROJECT_ROOT / "scripts" / "install" / "install.sh"
WINDOWS_INSTALL_SCRIPT = PROJECT_ROOT / "scripts" / "install" / "install.ps1"


def test_install_script_is_valid_posix_sh() -> None:
    subprocess.run(["sh", "-n", str(INSTALL_SCRIPT)], check=True)


def test_windows_install_script_is_valid_powershell() -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        return
    subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-Command",
            "$tokens=$null; $errors=$null; "
            "$null=[System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$tokens, [ref]$errors); "
            "if ($errors.Count) { $errors | Format-List; exit 1 }",
            str(WINDOWS_INSTALL_SCRIPT),
        ],
        check=True,
    )


def test_windows_install_script_checks_python_before_installing() -> None:
    script = WINDOWS_INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "Python 3.9+ is required" in script
    assert "https://www.python.org/downloads/windows/" in script
    assert "agsekit.cmd" in script


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


def test_wsl_multipass_symlink_warns_when_windows_multipass_missing(tmp_path: Path) -> None:
    script_body = INSTALL_SCRIPT.read_text(encoding="utf-8").replace('\nmain "$@"\n', "\n")
    fake_home = tmp_path / "home"
    missing_multipass = tmp_path / "missing" / "Multipass" / "bin" / "multipass.exe"

    fake_home.mkdir()

    driver = tmp_path / "driver.sh"
    driver.write_text(
        script_body
        + """
HOME=$1
PLATFORM=wsl
INSTALL_ROOT="$HOME/.local/share/agsekit"
BIN_DIR="$HOME/.local/bin"
SYMLINK_PATH="$BIN_DIR/agsekit"
MULTIPASS_SYMLINK_PATH="$BIN_DIR/multipass"
MULTIPASS_WINDOWS_INSTALL_URL="https://canonical.com/multipass/install"
WSL_MULTIPASS_EXE_FALLBACK=$2
PATH_HINT_NEEDED=0
PATH_FILES_CHANGED=0
PATH=/usr/bin:/bin

create_or_update_wsl_multipass_symlink
print_summary
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["sh", str(driver), str(fake_home), str(missing_multipass)],
        check=True,
        capture_output=True,
        text=True,
    )

    multipass_link = fake_home / ".local" / "bin" / "multipass"
    assert multipass_link.is_symlink()
    assert multipass_link.readlink() == missing_multipass
    assert (
        "Внимание! Multipass не установлен! Установите его скачав по ссылке "
        "https://canonical.com/multipass/install"
    ) in result.stdout
