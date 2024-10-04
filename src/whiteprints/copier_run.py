# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Run copier commands.

We use uvx.
"""

import itertools
from collections.abc import Iterable
from functools import cached_property

from whiteprints.uvx_run import UVX


class Copier:
    """Manage the copier command."""

    @cached_property
    def uvx(self) -> UVX:
        """A uvx manager.

        Returns:
            a uvx manager instance.
        """
        return UVX()

    def copy(
        self,
        command: Iterable[str],
        *,
        context: Iterable[str] = (),
        trust: bool = False,
    ) -> None:
        """Run a copier command.

        Args:
            command: arguments for the copier copy command.
            context: additional depenencies to inject.
            trust: copier trust for code execution.
        """
        command = [
            *itertools.chain.from_iterable(
                ("--with", package) for package in context
            ),
            "copier",
            "copy",
            *command,
        ] + (["--trust"] if trust else [])
        self.uvx.run(command)
