# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging configuration interface."""

from collections.abc import Mapping
from typing import Final, NamedTuple

from whiteprints.libconfig.config_loader import RawConfiguration
from whiteprints.redaction import SafeString
from whiteprints.toml_types import TOML


__all__: Final = ["LoggingConfiguration"]


class LoggingConfiguration(NamedTuple):
    """Holds the result of a logging configuration load.

    Attributes:
        raw_config: The raw TOML/text content of the configuration.
        substitutions: The template substitutions performed.
        is_default_config: True if using the built-in default configuration.
    """

    content: TOML
    raw_content: RawConfiguration
    substitutions: Mapping[str, SafeString | None]
    is_fallback: bool
