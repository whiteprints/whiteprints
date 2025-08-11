# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Defines debug command actions."""

from argparse import (
    ArgumentParser,
    Namespace,
)
from collections.abc import Sequence
from typing import (
    Final,
    NoReturn,
    cast,
    override,
)

from whiteprints.cli import robust_print_json
from whiteprints.cli.entrypoint_parser_action import CompleterAction
from whiteprints.exit_codes import ExitCode
from whiteprints.lazy_import import import_lazy_project


__all__: Final = ["Distributions", "Platform"]
"""Public module attributes."""


class Platform(CompleterAction):
    """Print current platform information."""

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Sequence[str] | str | None,
    ) -> NoReturn:
        """The action callback.

        Args:
            parser: the argument parser.
            namespace: the arguments namespace.
            args: the arguments passed to the parser.
        """
        redaction = import_lazy_project("redaction")
        flag_value = args[0]
        env = import_lazy_project("cli").ENV
        data = import_lazy_project("env_report").gather_platform_info(env)
        import_lazy_project("layered_env").abort_on_error(
            env,
            import_lazy_project("cli.logs").LOGGING.get_logger,
        )
        robust_print_json(
            data=data,
            indent=None,
            default=(
                redaction.safe_string_json_revealed
                if (
                    isinstance(flag_value, str)
                    and flag_value.lower() == "reveal"
                )
                else redaction.safe_string_json_redacted
            ),
        )
        cast("ExitCode", import_lazy_project("exit_codes").SUCCESS).exit()


class Distributions(CompleterAction):
    """Print program distributions."""

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Sequence[str] | str | None,
    ) -> NoReturn:
        """The action callback.

        Args:
            parser: the argument parser.
            namespace: the arguments namespace.
            args: the arguments passed to the parser.
        """
        redaction = import_lazy_project("redaction")
        flag_value = args[0]
        robust_print_json(
            data=import_lazy_project("env_report").gather_distributions(),
            indent=None,
            default=(
                redaction.safe_string_json_revealed
                if (
                    isinstance(flag_value, str)
                    and flag_value.lower() == "reveal"
                )
                else redaction.safe_string_json_redacted
            ),
        )
        cast("ExitCode", import_lazy_project("exit_codes").SUCCESS).exit()
