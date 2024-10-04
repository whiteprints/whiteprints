# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Localization."""

import gettext
import pathlib
from typing import Final


__all__: Final = ["LOCALE_DIRECTORY", "TRANSLATION", "_"]
"""Public module attributes."""


LOCALE_DIRECTORY: Final = pathlib.Path(__file__).parent / "locale"
"""Path to the directory containing the locales."""

TRANSLATION: Final = gettext.translation(
    "messages",
    LOCALE_DIRECTORY,
    fallback=True,
)
"""A Gettext translation."""

_: Final = TRANSLATION.gettext
"""Convenient access to Gettext's translation."""
