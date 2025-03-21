# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI logging."""

import json
from pathlib import Path

from whiteprints.cli.logs import setup_logging


def test_setup_logging(tmp_path: Path) -> None:
    """Test wether logging setup works."""
    log_config_path = tmp_path / "logs.json"

    # File does not exists so a new configuration is created
    setup_logging(log_config_path)
    assert json.loads(log_config_path.read_text()), (
        "logging configuration is not a valid json"
    )

    # Reload the created configuration for coverage
    setup_logging(log_config_path)
