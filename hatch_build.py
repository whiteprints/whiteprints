# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Hatch build hook for localization."""

import sys
from pathlib import Path

from babel.messages.frontend import OptionError
from babel.messages.setuptools_frontend import compile_catalog
from hatchling.builders.config import BuilderConfigBound
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


if sys.version_info < (3, 12):
    from typing_extensions import override
else:
    from typing import override


def _compile(locale_path: Path) -> None:
    """Compile a localization file."""
    cmd = compile_catalog()
    cmd.initialize_options()
    # Hatchling's typing sucks. We ignore this warning.
    cmd.directory = locale_path  # pyright: ignore [reportAttributeAccessIssue]
    cmd.use_fuzzy = True
    cmd.finalize_options()
    try:
        cmd.run()
    except OptionError:
        pass


class CustomBuildHook(BuildHookInterface[BuilderConfigBound]):
    """Custom Hatch builld hook for localization using PyBabel."""

    @override
    def initialize(
        self,
        version: str,
        build_data: dict[str, object],
    ) -> None:
        """Initialize the build hook."""
        for locale_path in map(
            Path,
            (
                "src/whiteprints/locale",
                "whiteprints/locale",
            ),
        ):
            if locale_path.is_dir():
                _compile(locale_path)
