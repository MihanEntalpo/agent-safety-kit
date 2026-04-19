import importlib.util
import urllib.error
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build" / "check_pypi_version.py"

spec = importlib.util.spec_from_file_location("check_pypi_version", SCRIPT_PATH)
assert spec is not None
check_pypi_version = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(check_pypi_version)


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_pypi_version_exists_returns_true_on_success() -> None:
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, timeout, request.headers))
        return FakeResponse()

    assert check_pypi_version.pypi_version_exists(
        "agsekit",
        "1.2.3",
        "https://pypi.org",
        timeout=3,
        opener=opener,
    )
    assert calls == [
        (
            "https://pypi.org/pypi/agsekit/1.2.3/json",
            3,
            {"User-agent": "agsekit-release-check"},
        )
    ]


def test_pypi_version_exists_returns_false_on_404() -> None:
    def opener(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    assert not check_pypi_version.pypi_version_exists(
        "agsekit",
        "9.9.9",
        "https://pypi.org",
        opener=opener,
    )


def test_pypi_version_exists_fails_on_non_404_http_error() -> None:
    def opener(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 500, "Server Error", {}, None)

    try:
        check_pypi_version.pypi_version_exists(
            "agsekit",
            "1.2.3",
            "https://pypi.org",
            opener=opener,
        )
    except check_pypi_version.PyPIVersionError as exc:
        assert "PyPI returned HTTP 500" in str(exc)
    else:
        raise AssertionError("non-404 PyPI HTTP errors should fail")


def test_read_project_name_version(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "agsekit"\nversion = "1.2.3"\n', encoding="utf-8")

    assert check_pypi_version.read_project_name_version(pyproject) == ("agsekit", "1.2.3")
