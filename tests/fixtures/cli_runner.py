# SPDX-FileCopyrightText: © 2024 The Whiteprints authors and contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""CLI runner fixture."""

import pytest
from click import testing


@pytest.fixture(scope="class")
def cli_runner() -> testing.CliRunner:
    """CLI Runner Fixture.

    Returns:
        A CliRunner instance.
    """
    return testing.CliRunner(mix_stderr=False)
