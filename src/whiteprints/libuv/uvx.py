# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Run uvx commands.

We use Python subprocesses.
"""

import importlib
from collections.abc import Iterable
from typing import Final


__all__: Final = ["UVX"]
"""Public module attributes."""


class UVX:
    """Manage the uv program."""

    def __init__(self) -> None:
        """Create an UVX instance."""
        self.bin = importlib.import_module("uv").find_uv_bin()

    def run(self, command: Iterable[str]) -> None:
        """Run `uv tool run`.

        Note:
            `uv tool run` is equivalent to `uvx`

        Args:
            command: The `uv tool run` command to execute.
            debug: run in debug mode. If debug is false, stderr is suppressed.

        Example:
            >>> UVX().run(["uv", "--help"])
            ...
            >>> UVX().run(["uv", "--help"], debug=True)
            ...
        """
        (subprocess := importlib.import_module("subprocess")).run(  # nosec
            [
                self.bin,
                "tool",
                "run",
                "--quiet",
                "--isolated",
                "--no-progress",
                *command,
            ],
            stderr=subprocess.PIPE,
            shell=False,
            check=True,
            text=True,
        )
