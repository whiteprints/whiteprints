# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI entrypoint."""

from click import testing

from whiteprints import package_metadata
from whiteprints.cli import __app_name__, entrypoint


class TestCLI:
    """Test the CLI."""

    @staticmethod
    def test_version(cli_runner: testing.CliRunner) -> None:
        """Check if the version printed by the CLI match the API one."""
        result = cli_runner.invoke(
            entrypoint.whiteprints,
            ["--version"],
        )
        assert result.exit_code == 0, "The CLI did not exit properly."

        version_match = (
            f"{__app_name__}, version {package_metadata.__version__}"
            == result.stdout.rstrip()
        )
        assert version_match, (
            "The python version returned by the CLI do not match the API"
            " version (given by __version__)."
        )

    @staticmethod
    def test_license(cli_runner: testing.CliRunner) -> None:
        """Check if the license flag exists."""
        result = cli_runner.invoke(
            entrypoint.whiteprints,
            ["--license"],
        )
        assert result.exit_code == 0, "The CLI did not exit properly."

    @staticmethod
    def test_help_flag_exists(cli_runner: testing.CliRunner) -> None:
        """Check if the version printed by the CLI match the API one."""
        result = cli_runner.invoke(
            entrypoint.whiteprints,
            ["--help"],
        )
        assert result.exit_code == 0, "The CLI did not exit properly."

    @staticmethod
    def test_default(cli_runner: testing.CliRunner) -> None:
        """Check if the CLI called with default arguments return prpperly.

        Args:
            cli_runner: the CLI test runner provided by typer.testing or a
                fixture.
        """
        result = cli_runner.invoke(entrypoint.whiteprints)
        assert result.exit_code == 0, "The CLI did not exit properly."
