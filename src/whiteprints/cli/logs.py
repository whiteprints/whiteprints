# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging configuration for the CLI."""

import importlib
from functools import cache
from typing import Final

from whiteprints import import_extra


__all__: Final = ["setup_logging", "user_log_config", "user_log_dir"]


@cache
def user_log_dir() -> str:
    """The default user log directory Path.

    The default path is given by `platformdirs.user_log_path`.
    If `platformdirs` is not installed, returns the current directory.

    Example:
        >>> user_log_dir()
        ...

    Returns:
        The path to the log directory.
    """
    if (platformdirs := import_extra("platformdirs")) is None:
        return importlib.import_module("os").getcwd()

    return platformdirs.user_log_dir(
        importlib.import_module(
            "whiteprints.metadata",
        ).DISTRIBUTION_NAME
    )


@cache
def user_log_config() -> str | None:
    """The default user logging configuration file Path.

    If platformdirs is not installed, returns None.
    Otherwise the configuration path is given by
    `platformdirs.user_config_path`.

    Returns:
        The path to the logging configuration file if `platformdirs` is
        installed, None otherwise.
    """
    if (platformdirs := import_extra("platformdirs")) is None:
        return None

    return importlib.import_module("os").path.join(
        platformdirs.user_config_dir(
            importlib.import_module(
                "whiteprints.metadata",
            ).DISTRIBUTION_NAME
        ),
        "logs.json",
    )


def _generate_configuration(log_config_path: str) -> None:
    """Generate a default logging configuration file.

    The special keyword $USER_LOG_DIR will be replaced by the path returned by
    the function `user_log_dir`.

    Args:
        log_config_path: path to the logging configuration file.
    """
    with open(log_config_path, "w", encoding="utf-8") as user_log_config_fh:
        default_logs_config = {
            "version": 1,
            "disable_existing_loggers": True,
            "formatters": {
                "struct_json": {
                    "class": "whiteprints.logs.formatters.JSONFormatter",
                    "datefmt": "%Y-%m-%dT%H:%M:%S",
                },
            },
            "handlers": {
                "stderr": {
                    "class": "logging.StreamHandler",
                    "level": "CRITICAL",
                    "stream": "ext://sys.stderr",
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "WARNING",
                    "filename": "$USER_LOG_DIR/debug.log",
                    "formatter": "struct_json",
                    "maxBytes": 4_000_000,
                    "backupCount": 4,
                },
            },
            "loggers": {
                "root": {
                    "level": "NOTSET",
                    "handlers": ["stderr", "file"],
                },
            },
        }

        importlib.import_module("json").dump(
            default_logs_config,
            user_log_config_fh,
            indent=4,
        )


def setup_logging(log_config_path: str | None = None) -> None:
    """Setup logging.

    It loads the configuration file specified in the arguments. If the file
    does not exists, it is created. If None, a basic default configuration is
    provided.

    Args:
        log_config_path: path to the logging configuration file.
    """
    logging = importlib.import_module("logging")
    if log_config_path is None:
        logging.basicConfig(level=logging.CRITICAL)
    else:
        os = importlib.import_module("os")
        if not os.path.isfile(log_config_path):
            os.makedirs(
                os.path.dirname(log_config_path) or os.getcwd(),
                exist_ok=True,
            )
            _generate_configuration(log_config_path)

        os.makedirs(user_log_dir(), exist_ok=True)
        with open(log_config_path, encoding="utf-8") as log_config_file:
            raw_config = log_config_file.read()

        importlib.import_module("logging.config").dictConfig(
            config=importlib.import_module("json").loads(
                importlib.import_module("string")
                .Template(raw_config)
                .substitute({"USER_LOG_DIR": user_log_dir()})
            )
        )

    logging.captureWarnings(capture=True)
