from click.testing import CliRunner

from agsekit_cli.cli import config_group
from agsekit_cli.commands.config_example import config_example_legacy_command
from agsekit_cli.commands.config_gen import config_gen_legacy_command


def test_config_example_is_primary_and_legacy_alias_warns(tmp_path):
    primary_path = tmp_path / "primary.yaml"
    legacy_path = tmp_path / "legacy.yaml"
    runner = CliRunner()

    primary = runner.invoke(config_group, ["example", str(primary_path)])
    legacy = runner.invoke(config_example_legacy_command, [str(legacy_path)])

    assert primary.exit_code == 0
    assert primary_path.exists()
    assert "deprecated" not in primary.output.lower()
    assert legacy.exit_code == 0
    assert legacy_path.exists()
    assert "config-example" in legacy.output
    assert "config example" in legacy.output


def test_config_gen_is_primary_and_legacy_alias_warns_in_non_interactive_mode():
    runner = CliRunner()

    primary = runner.invoke(config_group, ["gen", "--non-interactive"])
    legacy = runner.invoke(config_gen_legacy_command, ["--non-interactive"])

    assert primary.exit_code != 0
    assert "config gen" in primary.output
    assert legacy.exit_code != 0
    assert "config-gen" in legacy.output
    assert "config gen" in legacy.output
