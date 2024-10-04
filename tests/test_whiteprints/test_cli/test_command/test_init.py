# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI entrypoint."""

from pathlib import Path
from typing import Final

from click import testing

from whiteprints.cli import entrypoint


MISSING_COMMAND_EXIT_CODE: Final = 2


class TestCLI:
    """Test the CLI."""

    @staticmethod
    def test_init_help(cli_runner: testing.CliRunner) -> None:
        """Check if the command called with help argument return propperly.

        Args:
            cli_runner: the CLI test runner provided by typer.testing or a
                fixture.
        """
        result = cli_runner.invoke(
            entrypoint.whiteprints,
            ["init", "--help"],
        )
        assert result.exit_code == 0, "The CLI did not exit properly."

    @staticmethod
    def test_init(cli_runner: testing.CliRunner) -> None:
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

    @staticmethod
    def test_init_python(
        cli_runner: testing.CliRunner,
        *,
        tmp_path: Path,
    ) -> None:
        """Check if the command called no arguments return propperly.

        Args:
            cli_runner: the CLI test runner provided by typer.testing or a
                fixture.
            tmp_path: a temporary path in which the project will be created.
        """
        result = cli_runner.invoke(
            entrypoint.whiteprints,
            [
                "init",
                str(tmp_path),
                "--force",
                "--data",
                "project_name=My Awesome Project",
                "--data",
                "author=Romain Brault",
                "--data",
                "organisation=RomainBrault",
                "--data",
                "author_email=mail@romainbrault.com",
                "--data",
                "organisation_email=mail@romainbrault.com",
                "--data",
                "code_license_id=MIT-0 OR Apache-2.0",
                "--data",
                "resources_license_id=CC0-1.0",
                "--data",
                "copyright_holder=Romain Brault",
                "--data",
                "copyright_holder_email=mail@romainbrault.com",
                "--data",
                "line_length=79",
                "--data",
                "target_python_version=py39",
            ],
        )
        assert result.exit_code == 0, "The CLI did not exit properly."
