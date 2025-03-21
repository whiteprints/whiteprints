# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI entrypoint."""

import json
from typing import AnyStr

import pytest

from whiteprints.cli.entrypoint import entrypoint
from whiteprints.package_metadata import __version__


def test_help(capsys: pytest.CaptureFixture[AnyStr]) -> None:
    """Test wether a help flag exists and works."""
    with pytest.raises(SystemExit):
        entrypoint(["--help"])

    captured = capsys.readouterr()
    assert captured.out, "Could not print application help message"


def test_version(capsys: pytest.CaptureFixture[AnyStr]) -> None:
    """Test wether a version flag exists and works."""
    with pytest.raises(SystemExit):
        entrypoint(["--version"])

    captured = capsys.readouterr()
    assert captured.out.rstrip() == __version__, (
        "Printed version does not match library version"
    )


def test_debug_info(capsys: pytest.CaptureFixture[AnyStr]) -> None:
    """Test wether a debug-info flag exists and works."""
    with pytest.raises(SystemExit):
        entrypoint(["--debug-info"])

    captured = capsys.readouterr()
    assert json.loads(captured.out), (
        "Could not print application debug informations"
    )
