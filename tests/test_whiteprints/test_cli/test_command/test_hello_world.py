# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI entrypoint."""

from typing import Final

from click import testing

from whiteprints.cli import entrypoint


MISSING_COMMAND_EXIT_CODE: Final = 2


class TestCLI:
    """Test the CLI."""

    @staticmethod
    def test_hello_world(cli_runner: testing.CliRunner) -> None:
        """Check if the command called with default arguments return propperly.

        Args:
            cli_runner: the CLI test runner provided by typer.testing or a
                fixture.
        """
        result = cli_runner.invoke(
            entrypoint.whiteprints,
            ["hello-world"],
        )
        assert result.exit_code == 0, "The CLI did not exit properly."

    @staticmethod
    def test_helloworld(cli_runner: testing.CliRunner) -> None:
        """Check if calling a non existing command fail gracely.

        Args:
            cli_runner: the CLI test runner provided by typer.testing or a
                fixture.
        """
        result = cli_runner.invoke(
            entrypoint.whiteprints,
            ["30a212ea-815d-4659-bf8a-9cb467a11de1"],
        )
        assert (
            result.exit_code == MISSING_COMMAND_EXIT_CODE
        ), "The CLI did not exit properly."
