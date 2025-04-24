# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Defines CLI actions."""

import importlib
import os
import sys
from argparse import (
    Action,
    ArgumentParser,
    Namespace,
)
from collections.abc import Sequence
from typing import (
    Any,
    Callable,
    ClassVar,
    Final,
    NoReturn,
    Optional,
    Union,
)

from whiteprints import _, has_module
from whiteprints.cli import robust_print


if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


__all__: Final = [
    "CompleterAction",
    "Completion",
    "Copyright",
    "License",
]


class CompleterAction(Action):
    """An action that can use a completer (argcomplete)."""

    completer: Callable[..., Any]


class Completion(CompleterAction):
    """Print the code licenses information."""

    SUPPORTED_SHELLS: ClassVar = (
        "bash",
        "zsh",
        "tcsh",
        "fish",
        "powershell",
    )

    @staticmethod
    def _autodetect_shell(arg: Optional[Union[str, Sequence[str]]]) -> str:
        """Try to autotect the shell if not given.

        Example:
            >>> Completion._autodetect_shell("bash")
            bash
            >>> Completion._autodetect_shell(["bash"])
            bash
            >>> shell = Completion._autodetect_shell(None)
            assert isinstance(shell, str)

        Returns:
            The current shell name.
        """
        if arg is None:
            return importlib.import_module("shellingham").detect_shell()[0]

        if isinstance(arg, str):
            return arg

        return arg[0]

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Union[Sequence[str], str, None],
    ) -> NoReturn:
        """Generate the autocompletion code.

        Args:
            parser: the argument parser
            namespace: the arguments namespace
            args: the arguments passed to the parser
        """
        # Bandit has a false positive. Here shell is a string not a
        # boolean. More importantly it is not related to a subprocess
        # execution simply the shell choice for completion.
        robust_print(
            importlib.import_module("argcomplete.shell_integration")
            .shellcode([parser.prog], shell=self._autodetect_shell(args[0]))
            .strip()
        )
        sys.exit(os.EX_OK)


class Copyright(CompleterAction):
    """Print the code licenses information."""

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Union[Sequence[str], str, None],
    ) -> NoReturn:
        """Print the code copyright information.

        Args:
            parser: the argument parser
            namespace: the arguments namespace
            args: the arguments passed to the parser
        """
        robust_print(
            _(
                'Copyright © 2024 The "Whiteprints" contributors'
                " <whiteprints@pm.me>."
            )
        )
        sys.exit(os.EX_OK)


class License(CompleterAction):
    """Print the code licenses information."""

    @staticmethod
    def _check_sequence(
        args: Sequence[Union[Sequence[str], str, None]],
    ) -> Union[Sequence[str], str, None]:
        if not isinstance(arg_values := args[0], Sequence):
            error_message = _("error: invalid_argument")
            robust_print(
                f"[red]{error_message}[/]"
                if has_module("rich")
                else error_message,
            )
            sys.exit(os.EX_SOFTWARE)

        return arg_values

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Union[Sequence[str], str, None],
    ) -> None:
        """The action callback.

        Args:
            parser: the argument parser
            namespace: the arguments namespace
            args: the arguments passed to the parser
        """
        arg_values = self._check_sequence(args)

        license_files = importlib.import_module(
            "whiteprints.package_metadata",
        ).find_license_files()
        if not arg_values:
            robust_print(license_files[0].read_text(encoding="utf-8"))
            sys.exit(os.EX_OK)

        requested_license = str(arg_values[0])
        for license_path in license_files:
            if requested_license in license_path.stem:
                robust_print(license_path.read_text(encoding="utf-8"))
                sys.exit(os.EX_OK)

        error_message = _("error: license {} not found").format(
            requested_license
        )
        robust_print(
            f"[red]{error_message}[/]"
            if has_module("rich")
            else error_message,
        )
        sys.exit(os.EX_SOFTWARE)
