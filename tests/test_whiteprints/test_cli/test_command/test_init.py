# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI init subcommand."""

import os
from pathlib import Path

import pytest
from pytest import CaptureFixture

from whiteprints.cli.entrypoint import entrypoint


def test_help(capsys: CaptureFixture[str]) -> None:
    """Test wether a help flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["init", "--help"])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert captured.out, "Could not print init subcommand help message."


def test_init_fail_on_empty_args(
    capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    """Test that the init subcommand fails when given empty data."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["init", str(tmp_path), "--data"])

    assert ext.value.code == os.EX_SOFTWARE, "Unexpected exit code."

    captured = capsys.readouterr()
    assert captured.err, "Could not print init subcommand help message."


def init_dummy(capsys: CaptureFixture[str], tmp_path: Path) -> None:
    """Test that the init subcommand fails when given empty data."""
    with pytest.raises(SystemExit) as ext:
        entrypoint([
            "init",
            str(tmp_path),
            "--defaults",
            "--data",
            "project_name=My Awesome Project",
            "--data",
            "author=Whiteprints",
            "--data",
            "organisation=Whiteprints",
            "--data",
            "author_email=whiteprints@whiteprints.com",
            "--data",
            "code_license_id=MIT-0 OR Apache-2.0",
            "--data",
            "resources_license_id=CC0-1.0",
            "--data",
            "target_python_version=py313",
        ])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert captured.out, "Project generation failed."
