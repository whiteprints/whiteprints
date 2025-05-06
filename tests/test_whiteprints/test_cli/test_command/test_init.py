# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI init subcommand."""

import os

import pytest
from pytest import CaptureFixture

from whiteprints.cli.entrypoint import entrypoint


def test_help(capsys: CaptureFixture[str]) -> None:
    """Test wether a help flag exists and works."""
    with pytest.raises(SystemExit) as ext:
        entrypoint(["init", "--help"])

    assert ext.value.code == os.EX_OK, "Unexpected exit code."

    captured = capsys.readouterr()
    assert captured.out, "Could not print init subcommand help message"
