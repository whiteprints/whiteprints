# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# PYTHON_ARGCOMPLETE_OK

"""Command Line Interface app entrypoint."""

from argparse import ArgumentParser, Namespace
from types import ModuleType
from typing import Final, cast

from whiteprints.cli.logs.logging_exceptions import LoggingConfigurationError
from whiteprints.custom_exceptions import (
    WhiteprintsError,
    format_exception_chain,
)
from whiteprints.exit_codes import ExitCode
from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import (
    import_extra,
    import_lazy,
    import_lazy_project,
)
from whiteprints.libconfig.config_exceptions import ConfigLoaderError
from whiteprints.signals_handler import DelaySignals


__all__: Final = ["create_parser", "entrypoint"]
"""Public module attributes."""


(_ARGPARSE_GETTEXT := import_lazy("gettext")).bindtextdomain(
    "argparse",
    _.locale_directory,
)
_ARGPARSE_GETTEXT.textdomain("argparse")


def create_parser() -> tuple[ArgumentParser, dict[str, ArgumentParser]]:
    """Create the CLI parser.

    Returns:
        The CLI parser.
    """
    entrypoint_parser = import_lazy_project("cli.entrypoint_parser")
    parser = entrypoint_parser.create_entrypoint_parser()
    subparsers = parser.add_subparsers(
        title=_("Subcommands"),
        dest="cmd",
    )
    import_lazy_project("cli.command.init_parser").setup_init_parser(
        subparsers.add_parser(
            "init",
            formatter_class=parser.formatter_class,
            description=_("Initialize a Python project."),
            help=_("Initialize a Python project."),
            exit_on_error=False,
            add_help=False,
            allow_abbrev=False,
        )
    )
    import_lazy_project("cli.command.debug_parser").setup_debug_parser(
        subparsers.add_parser(
            "debug",
            formatter_class=parser.formatter_class,
            description=_(
                "Debug info and diagnostics."
                " This subcommand is intended for contributors."
            ),
            help=_("Debug info and diagnostics."),
            exit_on_error=False,
            add_help=False,
            allow_abbrev=False,
        )
    )
    return parser, subparsers.choices


def _redact_namespace(namespace: Namespace) -> None:
    redaction = import_lazy_project("redaction")
    os = import_lazy("os")
    if hasattr(namespace, "project_directory"):
        redactor = import_lazy_project("redactor")
        namespace.project_directory = redaction.Sensitive(
            namespace.project_directory,
            redactor.PathRedactor(),
            "namespace",
        )

    namespace.log_config = (
        None
        if namespace.log_config is None
        else redaction.Sensitive(
            os.path.normcase(
                os.path.abspath(os.path.expanduser(namespace.log_config))
            ),
            import_lazy_project("redactor").PathRedactor(),
            "namespace",
        )
    )


def _create_namespace(
    args: list[str] | None,
    argcomplete: ModuleType | None,
) -> tuple[ArgumentParser, dict[str, ArgumentParser], Namespace]:
    """Create a namespace from the arguments.

    Args:
        args: the command line arguments.
        argcomplete: an optional argcomplete module.

    Returns:
        The argument parser along with the namespace of parsed arguments.
    """
    parser, subparsers = create_parser()

    if argcomplete is not None:
        argcomplete.autocomplete(parser)

    import_lazy_project("cli.entrypoint_parser").resolve_flags(
        parser, namespace := parser.parse_args(args)
    )

    _redact_namespace(namespace)

    return parser, subparsers, namespace


def _setup_logging(namespace: Namespace) -> None:
    """Setup the logging.

    Use the configuration provided in the namespace.

    Args:
        parser: the arguments parser.
        namespace: the arguments namespace.
    """
    logs = import_lazy_project("cli.logs")
    cli = import_lazy_project("cli")
    try:
        logs.LOGGING.configure(
            cli.ENV,
            namespace.log_config,
        )
    except (
        ConfigLoaderError,
        LoggingConfigurationError,
    ) as configuration_error:
        logger = logs.LOGGING.get_logger()
        logger.critical(format_exception_chain(configuration_error))
        cast(
            "ExitCode", import_lazy_project("exit_codes").CONFIGURATION_ERROR
        ).log(logger).exit()

    logs.LOGGING.log_configuration()

    try:
        import_lazy_project("cli.logs.logging_workers").spawn()
    except WhiteprintsError as whiteprint_error:
        logger = logs.LOGGING.get_logger()
        logger.critical(format_exception_chain(whiteprint_error))
        cast("ExitCode", import_lazy_project("exit_codes").CANNOT_CREATE).log(
            logger
        ).exit(whiteprint_error)

    logger = logs.LOGGING.get_logger("whiteprints.env_report")
    lazy = import_lazy_project("logs.lazy_logrecord_value")
    logger.debug(
        "program started",
        extra={
            "env_report": lazy.LazyRecordValue(
                lambda: (
                    import_lazy_project("env_report").gather_platform_info(
                        cli.ENV.get("VIRTUAL_ENV"),
                    )
                )
            ),
            "distributions": lazy.LazyRecordValue(
                import_lazy_project("env_report").gather_distributions
            ),
            "namespace": namespace.__dict__,
        },
    )
    cli.ENV.set_logger(logs.LOGGING.get_logger("whiteprints.environment"))
    cli.ENV.log_debug()
    import_lazy_project("layered_env").abort_on_error(
        cli.ENV,
        import_lazy_project("cli.logs").LOGGING.get_logger,
    )

    import time

    start = time.time()
    import time
    from functools import partial
    from multiprocessing import Process

    from whiteprints.cli.logs.logging_config import Logging
    from whiteprints.concurrency import (
        is_main_process,
        is_main_thread,
        reset_all_mutated_classvars,
    )
    from whiteprints.logs.logs_exceptions import LogRecordDroppedError

    def shutdown(proc: Process):
        print("SHUTTING DOWN WORKER")
        can_run = is_main_thread() and is_main_process()
        if can_run and proc.is_alive():
            print("WORKER START JOIN")
            while True:
                proc.terminate()
                proc.join(0.1)
                print(proc)
                print(proc.exitcode, proc.is_alive())
                if not proc.is_alive():
                    break
            print("WORKER END JOIN")
            proc.close()
            print("WORKER END CLOSE")

        print("SHUTTING DOWN WORKER DONE")

    main_process_pid = import_lazy("os").getpid()

    def log_in_subprocess(logging_instance: Logging, label: str) -> None:
        """Subprocess that logs one critical message to a spawn queue."""
        reset_all_mutated_classvars()
        logging_instance.log_configuration()
        logger = logging_instance.get_logger(
            sub=f"swarm.{label}",
            env={},
        )
        #  logger = logging_instance.get_logger(sub=f"emergency")
        signal = import_lazy("signal")
        os = import_lazy("os")
        print(
            "WORKER SIGMASK",
            os.getpid(),
            signal.pthread_sigmask(signal.SIG_BLOCK, []),
        )  # Shows current block
        #  print(signal.get_signal(signal.SIGTERM))
        try:
            for i in range(100000):
                if i % 10000 == 0:
                    print(i)

                logger.critical(
                    f"[{label}] logging from subprocess",
                    extra={
                        "index": i,
                        "label": label,
                        "worker_pid": import_lazy("os").getpid(),
                        "logger_pid": lazy.LazyRecordValue(
                            import_lazy("os").getpid
                        ),
                        "main_process_pid": main_process_pid,
                        "time": import_lazy("time").time(),
                    },
                )
        except LogRecordDroppedError as e:
            print("DROPPED RECORD")
            logger = logging_instance.get_logger(
                sub="emergency",
                env={},
            )
            logger.handle(e.record)

        print("I FINISHED")

    # Launch a swarm of N processes
    swarm_size = 1
    procs: list[Process] = []
    for i in range(swarm_size):
        with DelaySignals():
            proc = Process(
                target=log_in_subprocess,
                name=f"worker_{i}",
                args=(logs.LOGGING, f"worker-{i}"),
                daemon=False,
            )
            ExitCode.atexit(partial(shutdown, proc))
            print("STARTING WORKER")
            proc.start()
            procs.append(proc)

    print(f"Time to spawn and join {swarm_size} workers:", time.time() - start)

    for proc in procs:
        proc.join()

    import_lazy_project("exit_codes").SUCCESS.exit()


def _call_command(
    subparsers: dict[str, ArgumentParser], namespace: Namespace
) -> None:
    """Call a command.

    This is done by lazily loading the whiteprint module named after the
    command and the calling a function with the same name as the module name.

    Args:
        subparsers: the entrypoint command parser.
        namespace: the arguments namespace.
    """
    command = import_lazy_project(f"cli.command.command_{namespace.cmd}")
    getattr(command, namespace.cmd)(subparsers[namespace.cmd], namespace)


def entrypoint(args: list[str] | None = None) -> int:
    """The Whiteprint CLI.

    Example:
        >>> import os
        >>>
        >>> try:
        >>>     entrypoint([])
        >>> except SystemExit as ext:
        >>>     assert ext.code == os.EX_OK
        ...

    Args:
        args: the arguments forwarded to argparse. For example sys.argv.

    Returns:
        success.
    """
    # Create parser and parse arguments
    _parser, subparsers, namespace = _create_namespace(
        args,
        import_extra("argcomplete"),
    )

    # Switch to logging user configuration
    _setup_logging(namespace)

    # call CLI Command
    _call_command(subparsers, namespace)
    logger = import_lazy_project("cli.logs").LOGGING.get_logger()
    return cast("ExitCode", import_lazy_project("exit_codes").SUCCESS).log(
        logger
    )
