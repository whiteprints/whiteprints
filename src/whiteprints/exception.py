# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Project specific exception."""

from typing import Final


__all__: Final = ["WhiteprintsError"]


class WhiteprintsError(Exception):
    """A base exception for the project.

    Example:
        >>> class NewError(ValueError, WhiteprintsError):
        >>>     ...
    """
