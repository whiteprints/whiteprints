# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the environment module."""

import os
from pathlib import Path

from whiteprints.environment import load_dotenv


def test_load_dotenv(tmp_path: Path) -> None:
    """Test that a dotenv file can be loaded.

    Args:
        tmp_path: a temporary directory path (fixture).
    """
    dotenv = tmp_path / ".env"
    dotenv.write_text("TEST=TEST")
    load_dotenv(dotenv)
    assert os.environ["TEST"] == "TEST", "Failed to load '.env' dotenv."
