# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Initialize a project using pure logic for testable copy operations."""

from argparse import ArgumentParser, Namespace
from typing import Final, NamedTuple, NoReturn, cast

from copier.errors import CopierAnswersInterrupt, CopierError

from whiteprints.exit_codes import ExitCode
from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import import_lazy, import_lazy_project


__all__: Final = ["init"]
"""Public module attributes."""


_GITHUB_EXTRAS: Final = {
    "pypi": "gh:whiteprints/template-github-publish-pypi.git",
    "codecov": "gh:whiteprints/template-github-codecov.git",
    "readthedocs": "gh:whiteprints/template-github-readthedocs.git",
    "protect_repository": (
        "gh:whiteprints/template-github-protect-repository.git"
    ),
}
"""Define the repository mapping from feature names to copier templates."""


class _CopierOperation(NamedTuple):
    """Descriptor for a copier operation."""

    repo: str
    dest: str
    trust: bool


def _requires_github_integration(namespace: Namespace) -> bool:
    """Check if the namespace call for GitHub integration.

    Args:
        namespace: flags for github, github_all, extras.

    Returns:
        True if the namespace call for GitHub integration, False otherwise.
    """
    return (
        bool(namespace.github)
        or bool(namespace.github_all)
        or any(bool(getattr(namespace, f)) for f in _GITHUB_EXTRAS)
    )


def _build_github_operation(
    project_directory: str,
    namespace: Namespace,
) -> list[_CopierOperation]:
    """Build copy operations for GitHub core and feature extras.

    Args:
        project_directory: target directory
        namespace: flags for github, github_all, extras.

    Returns:
        _CopierOperation list for GitHub actions


    Example:
        >>> from argparse import Namespace
        >>>
        >>> ns = Namespace(
        ...     github=True,
        ...     github_all=False,
        ...     pypi=False,
        ...     codecov=False,
        ...     readthedocs=False,
        ...     protect_repository=False
        ... )
        >>>
        >>> ops = _build_github_operation('proj', [], ns, ['ctx'])
        >>> [o.repo for o in ops]
        ['gh:whiteprints/template-github.git']
    """
    ops: list[_CopierOperation] = []

    if _requires_github_integration(namespace):
        ops.append(
            _CopierOperation(
                repo="gh:whiteprints/template-github.git",
                dest=project_directory,
                trust=True,
            )
        )

    # Add each extra feature template if requested or global flag
    for feature, repo in _GITHUB_EXTRAS.items():
        if bool(namespace.github_all) or bool(getattr(namespace, feature)):
            ops.append(
                _CopierOperation(
                    repo=repo,
                    dest=project_directory,
                    trust=True,
                )
            )
    return ops


def _build_copier_operation(
    project_directory: str,
    namespace: Namespace,
) -> list[_CopierOperation]:
    """Build a list of _CopierOperation instances based on feature flags.

    Args:
        project_directory: target directory for templates
        namespace: boolean flags for each feature

    Returns:
        a list of _CopierOperation objects describing the copy operations to
        perform.

    Example:
        >>> from argparse import Namespace
        >>>
        >>> ns = Namespace(
        ...     command_line=True,
        ...     github=False,
        ...     github_all=False,
        ...     pypi=False,
        ...     codecov=False,
        ...     readthedocs=False,
        ...     protect_repository=False
        ... )
        >>>
        >>> ops = _build_copier_operation('proj', [], ns)
        >>> [o.repo for o in ops]
        [..., 'gh:whiteprints/template-rich-click.git']
    """
    ops: list[_CopierOperation] = []

    # Base Python template
    ops.append(
        _CopierOperation(
            repo="gh:whiteprints/template-python.git",
            dest=project_directory,
            trust=True,
        )
    )

    # Optional CLI support
    if bool(namespace.command_line):
        ops.append(
            _CopierOperation(
                repo="gh:whiteprints/template-rich-click.git",
                dest=project_directory,
                trust=True,
            )
        )

    # Optional GitHub and GitHub extras support
    ops.extend(
        _build_github_operation(
            project_directory,
            namespace,
        )
    )
    return ops


def _exit_on_error(error: CopierError) -> NoReturn:
    logger = import_lazy_project("cli.logs").LOGGING.get_logger()
    exceptions = import_lazy_project("logs.logs_exceptions")
    logger.critical(
        str(error),
        **(
            exceptions.LogTraceConfig(
                stack_info=True,
                exc_info=error,
            )
            if logger.isEnabledFor(10)
            else exceptions.LogTraceConfig(stack_info=False, exc_info=None)
        ),
    )
    cast(
        "ExitCode", import_lazy_project("exit_codes").INTERNAL_SOFTWARE_ERROR
    ).log(logger).exit(error)


def _exit_on_copier_interrupt(
    copier_answers_interrupt: CopierAnswersInterrupt,
) -> NoReturn:
    logger = import_lazy_project("cli.logs").LOGGING.get_logger()
    exceptions = import_lazy_project("logs.logs_exceptions")
    logger.error(
        _("%s caught while running Copier"),
        type(copier_answers_interrupt).__name__,
        **(
            exceptions.LogTraceConfig(
                stack_info=True,
                exc_info=copier_answers_interrupt,
            )
            if logger.isEnabledFor(10)
            else exceptions.LogTraceConfig(stack_info=False, exc_info=None)
        ),
    )
    logger.info(_("Execution interrupted by user (KeyboardInterrupt)."))
    cast("ExitCode", import_lazy_project("exit_codes").SIG_INT).log(
        logger
    ).exit(copier_answers_interrupt)


def init(_parser: ArgumentParser, namespace: Namespace) -> None:
    """Initialize a python project by executing all copy operations."""
    copier_errors = import_lazy("copier.errors")
    plumbum_errors = import_lazy("plumbum.commands.processes")
    main = import_lazy("copier.main")
    try:
        for op in _build_copier_operation(
            namespace.project_directory.reveal,
            namespace,
        ):
            with main.Worker(
                src_path=op.repo,
                dst_path=op.dest,
                unsafe=op.trust,
            ) as worker:
                worker.run_copy()
    except copier_errors.CopierAnswersInterrupt as copier_answers_interrupt:
        _exit_on_copier_interrupt(copier_answers_interrupt)
    except (
        copier_errors.CopierError,
        plumbum_errors.ProcessExecutionError,
    ) as copier_error:
        _exit_on_error(copier_error)
