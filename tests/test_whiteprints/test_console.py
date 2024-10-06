# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the console module."""

from rich import console as rich_console

from whiteprints import console as whiteprint_console


def test_default_stdout_console() -> None:
    """Check that the STDOUT console is a rich console instance."""
    assert isinstance(whiteprint_console.STDOUT, rich_console.Console)


def test_default_stderr_console() -> None:
    """Check that the STDERR console is a rich console instance."""
    assert isinstance(whiteprint_console.STDERR, rich_console.Console)
