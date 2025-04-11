# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Project specific exception."""


class WhiteprintsError(Exception):
    """A base exception for the project.

    Example:
        >>> class NewError(ValueError, WhiteprintsError):
        >>>     ...
    """


class NotAPackageError(WhiteprintsError, ValueError):
    """The current project is not a package."""
