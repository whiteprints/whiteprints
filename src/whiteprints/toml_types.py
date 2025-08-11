# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import date, datetime, time
from typing import Final


__all__: Final = [
    "TOML",
    "TOMLScalar",
]


type TOMLScalar = bool | int | float | str | date | time | datetime
"""A type representing valid scalar values in TOML configuration files.

This type includes the following possible values:
- `bool`: Boolean values.
- `int`: Integer values.
- `float`: Floating-point numbers.
- `str`: String values.
- `date`: Date objects.
- `time`: Time objects.
- `datetime`: DateTime objects.

This type is used to represent any of the possible scalar values that can be
used in TOML files.
"""

type TOML = dict[str, TOML] | list[TOML] | TOMLScalar
"""A type representing valid TOML structures (including nested).

This type can represent:
- A dictionary with string keys and TOML values (nested structure).
- A list of TOML values (lists of scalars or nested structures).
- A single scalar value of type `TOMLScalar`.

This type is used to represent complex structures and values in TOML files.
"""
