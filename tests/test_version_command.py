from click.testing import CliRunner

from agsekit_cli.commands import version as version_command


def test_version_command_reports_installed_and_project(monkeypatch):
    monkeypatch.setattr(version_command, "_installed_version", lambda: "2.3.4")
    monkeypatch.setattr(version_command, "_find_pyproject_version", lambda: "1.2.3")

    runner = CliRunner()
    result = runner.invoke(version_command.version_command, [])

    assert result.exit_code == 0
    assert "Installed version: 2.3.4" in result.output
    assert "Project version: 1.2.3" in result.output


def test_version_command_project_only(monkeypatch):
    monkeypatch.setattr(version_command, "_installed_version", lambda: None)
    monkeypatch.setattr(version_command, "_find_pyproject_version", lambda: "3.0.0")

    runner = CliRunner()
    result = runner.invoke(version_command.version_command, [])

    assert result.exit_code == 0
    assert "Installed version:" not in result.output
    assert "Project version: 3.0.0" in result.output
