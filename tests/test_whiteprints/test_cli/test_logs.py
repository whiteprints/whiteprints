# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the CLI logging."""

import json
from pathlib import Path

import pytest

from whiteprints.cli.logs import setup_logging


def test_setup_logging(tmp_path: Path) -> None:
    """Test wether logging setup works."""
    log_config_path = tmp_path / "logs.json"

    # File does not exists so a new configuration is created
    setup_logging(str(log_config_path))
    generated_config = log_config_path.read_text(encoding="utf-8")
    assert json.loads(generated_config), (
        "logging configuration is not a valid json"
    )

    # Reload the created configuration for coverage
    setup_logging(str(log_config_path))
    assert log_config_path.read_text() == generated_config, (
        "logging configuration should not be modified when reloaded"
    )


@pytest.mark.extras_and_no_extras
def test_setup_logging_no_config() -> None:
    """Test wether logging setup works when no logs config is given."""
    setup_logging()
