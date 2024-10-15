# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Initialize a project (interface)."""

from typing import Final, TypedDict


__all__: Final = ["InitKwargs"]


class InitKwargs(TypedDict):
    """The 'init' command line arguments."""

    command_line: bool
    github: bool
    pypi: bool
    codecov: bool
    readthedocs: bool
    protect_repository: bool
    github_all: bool
