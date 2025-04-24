# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI entrypoint."""

import json
import os

import pytest

from whiteprints.cli.entrypoint import entrypoint
from whiteprints.cli.entrypoint_parser import Completion
from whiteprints.package_metadata import find_version


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a help flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--help"])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert captured.out, "Could not print application help message"


def test_wrong_usage(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether the app handles properly wrong usage."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--this-flag-does-not-exists"])

    assert ext.value.code == os.EX_USAGE, "Unexpected exit code."

    captured = capsys.readouterr()
    assert "error" in captured.err, "Could not print application help message"


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a version flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--version"])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert captured.out.rstrip() == find_version(), (
        "Printed version does not match library version"
    )


@pytest.mark.no_extras
def test_platform(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a platform flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--platform"])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert json.loads(captured.out), (
        "Could not print application debug informations"
    )


@pytest.mark.no_extras
def test_platform_full(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a platform flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--platform", "--platform"])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert json.loads(captured.out), (
        "Could not print application debug informations"
    )


def test_copyright(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a copyright flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--copyright"])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert captured.out, "Could not print application copyright message"


def test_license_simple(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a license flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--license"])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert captured.out, "Could not print application license informations"


def test_license_full(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a license flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--license", "--license"])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert json.loads(captured.out), (
        "Could not print application license informations"
    )


def test_license_valid(capsys: pytest.CaptureFixture[str]) -> None:
    """Test wether a license text flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--license-text"])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert captured.out, "There should be a license text displayed"


@pytest.mark.no_extras
def test_shell_autocompletion_fail_when_no_extras(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that autocompletion flag is unavailable when no extras."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--autocompletion-script"])

    assert ext.value.code == os.EX_USAGE, "Unexpected exit code."

    captured = capsys.readouterr()
    assert "error" in captured.err.lower(), (
        "There should be an error when trying to get an autocompletion script"
        " when extra `qol` is not installed"
    )


def test_shell_autocompletion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test wether an autocompletion-script flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--autocompletion-script", Completion.SUPPORTED_SHELLS[0]])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert captured.out, "There should be a shell autocompletion displayed"


def test_shell_autocompletion_auto(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test wether an autocompletion-script flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["--autocompletion-script"])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert captured.out, "There should be a shell autocompletion displayed"
