# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI actions."""

import pytest

from whiteprints.cli import PosixExitCode
from whiteprints.cli.action import Completion


def test_completion_action_shell_detection_failed() -> None:
    """Test the completion action on shell detection failure."""
    with pytest.raises(SystemExit) as ext:
        Completion.autodetect_shell(
            None,
            lambda: exec(
                "raise"
                ' importlib.import_module("shellingham").ShellDetectionFailure'
            ),
        )

    assert ext.value.code == PosixExitCode.SERVICE_UNAVAILABLE
