# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI entrypoint."""

import json

import pytest

from whiteprints.cli.entrypoint import entrypoint
from whiteprints.cli.entrypoint_parser import Completion
from whiteprints.package_metadata import __license_file__, __version__


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a help flag exists and works."""
    with pytest.raises(SystemExit):
        entrypoint(["--help"])

    captured = capsys.readouterr()
    assert captured.out, "Could not print application help message"


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a version flag exists and works."""
    with pytest.raises(SystemExit):
        entrypoint(["--version"])

    captured = capsys.readouterr()
    assert captured.out.rstrip() == __version__, (
        "Printed version does not match library version"
    )


def test_debug(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a debug flag exists and works."""
    with pytest.raises(SystemExit):
        entrypoint(["--debug"])

    captured = capsys.readouterr()
    assert json.loads(captured.out), (
        "Could not print application debug informations"
    )


def test_copyright(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a copyright flag exists and works."""
    with pytest.raises(SystemExit):
        entrypoint(["--copyright"])

    captured = capsys.readouterr()
    assert captured.out, "Could not print application copyright message"


def test_license(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a license flag exists and works."""
    with pytest.raises(SystemExit):
        entrypoint(["--license"])

    captured = capsys.readouterr()
    assert json.loads(captured.out), (
        "Could not print application license informations"
    )


def test_license_invalid(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a license flag exists and works."""
    with pytest.raises(SystemExit):
        entrypoint(["--license", "SHOULD-NOT_BE-A-VALID-SPDX-IDENTIFIER"])

    captured = capsys.readouterr()
    assert "error" in captured.err.lower(), (
        "There should be an error message on invalid license choice"
    )


def test_license_valid(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a license flag exists and works."""
    impossible_license_name = "-".join([
        path.stem for path in __license_file__
    ])
    with pytest.raises(SystemExit):
        entrypoint(["--license", impossible_license_name])

    captured = capsys.readouterr()
    assert captured.out, "There should be a license text displayed"


def test_completion_fail_with_no_extras(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test wether a completion-script flag exists and works."""
    with pytest.raises(SystemExit):
        entrypoint(["--completion-script", Completion.SUPPORTED_SHELLS[0]])

    captured = capsys.readouterr()
    assert "error" in captured.err.lower(), (
        "There should be an error when trying to get a completion script"
        " when extra `qol` is not installed"
    )
