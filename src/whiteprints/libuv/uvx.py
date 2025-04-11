# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Run uvx commands.

We use Python subprocesses.
"""

import subprocess  # nosec
from collections.abc import Iterable
from functools import cached_property
from pathlib import Path
from typing import Final

import uv


__all__: Final = ["UVX"]


class UVX:
    """Manage the uv program."""

    @cached_property
    def bin(self) -> Path:
        """The uv binary path.

        Example:
            >>> UVX().bin
            PosixPath(...)

        Returns:
            a path to the uv binary.
        """
        return Path(uv.find_uv_bin())

    def run(self, command: Iterable[str]) -> None:
        """Run `uv tool run`.

        Note:
            `uv tool run` is equivalent to `uvx`

        Example:
            >>> UVX().run(["uv", "--help"])
            ...

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
