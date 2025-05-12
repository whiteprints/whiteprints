# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI actions."""

import importlib

from whiteprints.cli.action import Completion


def _always_invalid_shell() -> None:
    """Simulate a missing shell.

    When shellingham is not found it returns None. Otherwise it raises a
    ShellDetectionFailure.
    """
    try:
        shellingham = importlib.import_module("shellingham")
    except ModuleNotFoundError:
        return

    raise shellingham.ShellDetectionFailure


def test_completion_action_shell_detection_failed() -> None:
    """Test the completion action on shell detection failure."""
    Completion.autodetect_shell(
        None,
        _always_invalid_shell,
    )
