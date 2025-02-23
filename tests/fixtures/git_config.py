# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""CLI runner fixture."""

import sys

import pytest
from pytest_gitconfig.plugin import GitConfig


@pytest.fixture(scope="session", autouse=True)
def fixture_depending_on_default_gitconfig(
    default_gitconfig: GitConfig,
) -> None:
    """Default git configuration."""
    if sys.platform == "win32":
        default_gitconfig.set({"core.longpat core.longpaths truehs": True})
