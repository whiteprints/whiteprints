# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Defines CLI actions."""

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
    cast,
    override,
)

from whiteprints.cli import robust_print, robust_print_json
from whiteprints.exit_codes import ExitCode
from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import import_lazy, import_lazy_project


__all__: Final = [
    "CompleterAction",
    "Completion",
    "Copyright",
    "License",
    "LicenseText",
    "Reuse",
    "Version",
]
"""Public module attributes."""


class CompleterAction(Action):
    """An action that can use a completer (argcomplete)."""

    completer: Callable[..., Any]
    """An additional completer added to the Action.

    This is here to help type checkers. Indeed argcomplete dynamically injects
    a completer attribute which his not present int the argparse.Action. As a
    results linters complains when assinging a completer to an Action.
    """


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
    def _abort_shell_detection() -> NoReturn:
        """Abort shell detection."""
        error_message = (
            "Failed to auto-detect your shell. "
            "Run `whiteprints --autocompletion-script <shell_name>` instead."
        )

        logger = import_lazy_project("cli.logs").LOGGING.get_logger()
        logger.critical(error_message)
        cast(
            "ExitCode", import_lazy_project("exit_codes").SERVICE_UNAVAILABLE
        ).log(logger).exit()

    @classmethod
    def autodetect_shell(
        cls,
        args: str | Sequence[str] | None,
        shell_detection_function: Callable[[], tuple[str, str] | None],
    ) -> str | None:
        """Try to autotect the shell if not given.

        Args:
            args: the arguments forwarded to the action.
            shell_detection_function: a callable that takes no args and return
                a tuple containing the shell name and the command to invoke it.
                E.g. `(sh, /bin/sh)`.

        Returns:
            The current shell name.

        Example:
            >>> def _always_sh() -> tuple[str, str]:
            ...     return ("sh", "/bin/sh")
            >>>
            >>> Completion.autodetect_shell(None, _always_sh)
            sh
            >>> Completion.autodetect_shell("sh", _always_sh)
            sh
            >>> Completion.autodetect_shell(["sh"], _always_sh)
            sh
        """
        if args:
            return args if isinstance(args, str) else args[0]

        try:
            shell = shell_detection_function()
        except import_lazy("shellingham").ShellDetectionFailure:
            cls._abort_shell_detection()

        return shell[0] if shell else shell

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
            import_lazy("argcomplete.shell_integration")
            .shellcode(
                [parser.prog],
                shell=self.autodetect_shell(  # nosec
                    args[0],
                    import_lazy("shellingham").detect_shell,
                ),
            )
            .strip()
        )
        cast("ExitCode", import_lazy_project("exit_codes").SUCCESS).exit()


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
        cast("ExitCode", import_lazy_project("exit_codes").SUCCESS).exit()


class Version(CompleterAction):
    """Print the program version."""

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
            import_lazy_project("fast_distinfo_reader").extract_field(
                "Version"
            )
        )
        cast("ExitCode", import_lazy_project("exit_codes").SUCCESS).exit()


class License(CompleterAction):
    """Print the code licenses."""

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
        robust_print(
            import_lazy_project("fast_distinfo_reader").extract_field(
                "License-Expression"
            )
        )
        cast("ExitCode", import_lazy_project("exit_codes").SUCCESS).exit()


class Reuse(CompleterAction):
    """Print the code licenses."""

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
        license_expression = import_lazy_project(
            "fast_distinfo_reader"
        ).extract_field("License-Expression")
        robust_print_json(
            data={
                "SPDX-License-Identifier": license_expression,
                "DISCLAIMER": _(
                    "This project is REUSE compliant."
                    " Check the SPDX header of each"
                    " individual source code file"
                    " for detailed licensing information."
                ).format(),
                "source_code_location": str(
                    (os := import_lazy("os")).path.dirname(
                        os.path.dirname(__file__)
                    )
                ),
                "REUSE": "https://reuse.software/",
            },
            indent=None,
        )
        cast("ExitCode", import_lazy_project("exit_codes").SUCCESS).exit()


class LicenseText(CompleterAction):
    """Print the code licenses text."""

    @staticmethod
    def _print(args: Sequence[str] | str | None) -> None:
        """Print the license text.

        Args:
            args: the license name to print.

        Example:
            >>> from whiteprints.fast_distinfo_reader import extract_fields
            >>>
            >>> license_file = next(iter(extract_fields("License-File")))
            >>> LicenseText._print(license_file)
            ...
            >>> LicenseText._print([license_file])
            ...
            >>> LicenseText._print(None)
            ...
            >>> LicenseText._print("")
            ...
            >>> LicenseText._print([""])
            ...
        """
        license_paths = import_lazy_project(
            "fast_distinfo_reader"
        ).extract_fields("License-File")
        licenses_directory = (os := import_lazy("os")).path.join(
            import_lazy_project(
                "fast_distinfo_reader"
            ).locate_dist_info_directory(),
            "licenses",
        )

        # package with a single license
        if not args or isinstance(args, str):
            with open(
                os.path.join(licenses_directory, next(iter(license_paths))),
                encoding="UTF-8",
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
                    encoding="UTF-8",
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

        Args:
            parser: the argument parser.
            namespace: the arguments namespace.
            args: the arguments passed to the parser.
        """
        self._print(args[0])
        cast("ExitCode", import_lazy_project("exit_codes").SUCCESS).exit()
