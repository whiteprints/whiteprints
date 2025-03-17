# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging configuration for the CLI."""

import importlib
from functools import cache
from pathlib import Path
from typing import Final, Optional


__all__: Final = ["setup_logging", "user_log_config", "user_log_dir"]


@cache
def user_log_dir() -> Path:
    """The default user log directory Path.

    The default path is given by `platformdirs.user_log_path`.

    Returns:
        The path to the log directory.
    """
    return importlib.import_module("platformdirs").user_log_path(
        importlib.import_module(
            "whiteprints.cli.app_metadata",
            __package__,
        ).app_name()
    )


@cache
def user_log_config() -> Path:
    """The default user logging configuration file Path.

    The default path is given by `platformdirs.user_config_path`.

    Returns:
        The path to the logging configuration file.
    """
    return (
        importlib.import_module("platformdirs").user_config_path(
            importlib.import_module(
                "whiteprints.cli.app_metadata",
                __package__,
            ).app_name()
        )
        / "logs.json"
    )


def _generate_configuration(log_config_path: Path) -> None:
    """Generate a default logging configuration file.

    Args:
        log_config_path: path to the logging configuration file.
    """
    with log_config_path.open("w", encoding="utf-8") as user_log_config_fh:
        importlib.import_module("json").dump(
            {
                "version": 1,
                "disable_existing_loggers": True,
                "formatters": {
                    "struct_json": {
                        "class": "whiteprints.logs.formatters.JSONFormatter",
                        "datefmt": "%Y-%m-%dT%H:%M:%S",
                    }
                },
                "handlers": {
                    "stderr": {
                        "class": (
                            "whiteprints.logs.rich_json_handler.RichJSONHandler"
                        ),
                        "formatter": "struct_json",
                    }
                },
                "loggers": {
                    "root": {
                        "level": "WARNING",
                        "handlers": ["stderr"],
                    },
                },
            },
            user_log_config_fh,
            indent=4,
        )


def setup_logging(log_config_path: Optional[Path] = None) -> None:
    """Setup logging.

    It loads the configuration file specified in the arguments. If the file
    does not exists, it is created.

    Args:
        log_config_path: path to the logging configuration file.
    """
    log_config_path = log_config_path or user_log_config()

    if not log_config_path.is_file():
        log_config_path.parent.mkdir(parents=True, exist_ok=True)
        _generate_configuration(log_config_path)

    user_log_dir().mkdir(parents=True, exist_ok=True)
    raw_config = log_config_path.read_text(encoding="utf-8")
    importlib.import_module("logging.config").dictConfig(
        config=importlib.import_module("json").loads(
            importlib.import_module("string")
            .Template(raw_config)
            .substitute({"USER_LOG_DIR": user_log_dir()})
        )
    )
    importlib.import_module("logging").captureWarnings(capture=True)
