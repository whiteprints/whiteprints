# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Default logging configuration constants for Whiteprints CLI."""

from typing import Final

from whiteprints.package_constants import DISTRIBUTION_NAME


__all__: Final = ["DEFAULT_LOG_CONFIG"]
"""Public module attributes."""


_DISTRIBUTION_NAME = DISTRIBUTION_NAME.upper()
"""Distribution name in uppercase."""

DEFAULT_LOG_CONFIG = f"""
version = 1
disable_existing_loggers = false

[filters.redact_traceback_and_stacktrace]
"()" = "{DISTRIBUTION_NAME}.logs.filters.RedactedTracebackAndStackTraceFilter"
traceback_mode = "hash"
stacktrace_mode = "path_redact"

[formatters.struct]
"()" = "{DISTRIBUTION_NAME}.logs.formatters.StructFormatter"
fmt = "%(message)s"
datefmt = "%Y-%m-%dT%H:%M:%S"
structured = "${{{_DISTRIBUTION_NAME}_LOG_STRUCT}}"
rich_pprint = false

[handlers.default]
class = "{DISTRIBUTION_NAME}.logs.handlers.StreamHandler"
formatter = "struct"
stream = "${{{_DISTRIBUTION_NAME}_LOG_STREAM}}"

[handlers.default.rich_handler_params]
show_time = false
show_level = false
show_path = false
rich_tracebacks = true

[root]
level = "${{{_DISTRIBUTION_NAME}_LOG_LEVEL}}"
handlers = ["default"]

[loggers]
"""
