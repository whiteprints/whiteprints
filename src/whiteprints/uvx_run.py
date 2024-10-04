# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Run uvx commands.

We use Python subprocesses.
"""

import subprocess  # nosec
from collections.abc import Iterable
from functools import cached_property
from pathlib import Path

import uv


class UVX:
    """Manage the uv program."""

    @cached_property
    def bin(self) -> Path:
        """The uv binary path.

        Returns:
            a path to the uv binary.
        """
        return Path(uv.find_uv_bin())

    def run(self, command: Iterable[str]) -> None:
        """Run `uv tool run`.

        Note:
            `uv tool run` is equivalent to `uvx`

        Args:
            command: The `uv tool run` command to execute.
        """
        subprocess.run(  # nosec
            [
                self.bin,
                "tool",
                "run",
                *command,
            ],
            shell=False,
            check=True,
        )
