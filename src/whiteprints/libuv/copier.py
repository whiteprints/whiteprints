# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Run copier commands.

We use uvx.
"""

import itertools
from collections.abc import Iterable
from typing import Final

from whiteprints.libuv.uvx import uvx


__all__: Final = ["copy"]
"""Public module attributes."""


def copy(
    command: Iterable[str],
    *,
    context: Iterable[str] = (),
    trust: bool = False,
) -> None:
    """Run a copier command.

    Example:
        >>> Copier().copy(["--help"])
        ...

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
    uvx(command)
