# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Defines CLI actions."""

import importlib
import sys
from argparse import (
    Action,
    ArgumentParser,
    Namespace,
)
from collections.abc import Callable, Sequence
from typing import (
    Any,
    ClassVar,
    Final,
    NoReturn,
)

from whiteprints import _
from whiteprints.cli import PosixExitCode, robust_print


if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


__all__: Final = [
    "CompleterAction",
    "Completion",
    "Copyright",
    "License",
    "Version",
]
"""Public module attributes."""


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
    def _autodetect_shell(args: str | Sequence[str] | None) -> str:
        """Try to autotect the shell if not given.

        Args:
            args: the arguments forwarded to the action.

        Returns:
            The current shell name.

        Example:
            >>> Completion._autodetect_shell("bash")
            bash
            >>> Completion._autodetect_shell(["bash"])
            bash
            >>> assert isinstance(Completion._autodetect_shell(None), str)
        """
        if args is None:
            return importlib.import_module("shellingham").detect_shell()[0]

        if isinstance(args, str):
            return args

        return args[0]

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Sequence[str] | str | None,
    ) -> NoReturn:
        """Generate the autocompletion code.

        Args:
            parser: the argument parser.
            namespace: the arguments namespace.
            args: the arguments passed to the parser.
        """
        # Bandit has a false positive. Here shell is a string not a
        # boolean. More importantly it is not related to a subprocess
        # execution simply the shell choice for completion.
        robust_print(
            importlib.import_module("argcomplete.shell_integration")
            .shellcode(
                [parser.prog],
                shell=self._autodetect_shell(args[0]),  # nosec
            )
            .strip()
        )
        PosixExitCode.SUCCESS.exit()


class Copyright(CompleterAction):
    """Print the code licenses information."""

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Sequence[str] | str | None,
    ) -> NoReturn:
        """Print the code copyright information.

        Args:
            parser: the argument parser.
            namespace: the arguments namespace.
            args: the arguments passed to the parser.
        """
        robust_print(
            _(
                'Copyright © 2024 The "Whiteprints" contributors'
                " <whiteprints@pm.me>."
            )
        )
        PosixExitCode.SUCCESS.exit()


class Version(CompleterAction):
    """Print the code licenses information."""

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Sequence[str] | str | None,
    ) -> NoReturn:
        """Print the code copyright information.

        Args:
            parser: the argument parser.
            namespace: the arguments namespace.
            args: the arguments passed to the parser.
        """
        robust_print(
            importlib.import_module(
                "whiteprints.metadata",
            ).extract_field("Version")
        )
        PosixExitCode.SUCCESS.exit()


class License(CompleterAction):
    """Print the code licenses information."""

    @staticmethod
    def _print_license_text(args: Sequence[str] | str | None) -> None:
        """Print the license text.

        Args:
            args: the license name to print.

        Example:
            >>> from whiteprints.metadata import extract_fields
            >>>
            >>> license_file = next(iter(extract_fields("License-File")))
            >>> License._print_license_text(license_file)
            ...
            >>> License._print_license_text([license_file])
            ...
            >>> License._print_license_text(None)
            ...
            >>> License._print_license_text("")
            ...
            >>> License._print_license_text([""])
            ...
        """
        license_paths = importlib.import_module(
            "whiteprints.metadata",
        ).extract_fields("License-File")
        licenses_directory = (os := importlib.import_module("os")).path.join(
            importlib.import_module(
                "whiteprints.metadata"
            ).locate_dist_info_directory(),
            "licenses",
        )

        # package with a single license
        if not args or isinstance(args, str):
            with open(
                os.path.join(licenses_directory, next(iter(license_paths))),
                encoding="utf-8",
            ) as license_file:
                text = license_file.read()

            robust_print(text)
            return

        # package with multiple licenses
        requested_license = args[0]
        for license_path in license_paths:
            if requested_license in os.path.basename(license_path):
                with open(
                    os.path.join(
                        licenses_directory,
                        license_path,
                    ),
                    encoding="utf-8",
                ) as license_file:
                    text = license_file.read()

                robust_print(text)
                return

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Sequence[str] | str | None,
    ) -> NoReturn:
        """The action callback.

        If the arguments values is empty, there is only a signle license to
        print, the one defined in the package.

        If the arguments is a sequence it means that the package have multiple
        licenses. Then the arguments should contains a single element,
        which correspond to the requested license to print among the licenses
        present in the package.

        Args:
            parser: the argument parser.
            namespace: the arguments namespace.
            args: the arguments passed to the parser.
        """
        self._print_license_text(args[0])
        PosixExitCode.SUCCESS.exit()
