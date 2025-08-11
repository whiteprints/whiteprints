# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level module."""

import importlib
from contextlib import AbstractContextManager
from functools import cached_property
from types import FrameType, TracebackType
from typing import Any, ClassVar, Final, override

from whiteprints.concurrency import has_mutated_classvars, is_main_thread


__all__: Final = ["DelaySignals"]
"""Public module attributes."""


@has_mutated_classvars
class DelaySignals(AbstractContextManager[None]):
    """Context manager to delay SIGINT and SIGTERM during critical sections.

    This context manager delays the specified signals (SIGINT and SIGTERM by
    default) during critical operations to prevent interruptions. On POSIX
    systems, the signals are blocked using `pthread_sigmask`, and on non-POSIX
    systems, signal handlers are overridden temporarily.

    Attributes:
        signals: The set of signals to delay (default SIGINT and SIGTERM).
    """

    __slots__ = ("_signal", "_use_masking", "signals")

    _depth: ClassVar[dict[int, int]] = {}
    """Tracks the depth of blocking for each signal."""

    _global_caught: ClassVar[list[int]] = []
    """Holds a list of signals that were caught during the context."""

    _global_original: ClassVar[dict[int, Any]] = {}
    """Holds the original signal handlers to restore them later."""

    @classmethod
    def reset_class(cls) -> None:
        """Reset the class-level variables to their initial state.

        This method clears all internal signal handling states, including
        signal depth, caught signals, and original handlers.
        """
        if is_main_thread():
            cls._depth = {}
            cls._global_caught = []
            cls._global_original = {}

    def __init__(self, signals: set[int] | None = None) -> None:
        """Initialize the DelaySignals context manager.

        Args:
            signals: A set of signals to delay (default SIGINT and SIGTERM).
        """
        self._signal = importlib.import_module("signal")
        self.signals = (
            {self._signal.SIGINT, self._signal.SIGTERM}
            if signals is None
            else signals
        )
        self._use_masking = hasattr(self._signal, "pthread_sigmask")

    def _block(self, sig: int) -> None:
        """Block the specified signal.

        Args:
            sig: The signal to block (e.g., `SIGINT`, `SIGTERM`).
        """
        try:
            if self._use_masking:
                self._signal.pthread_sigmask(self._signal.SIG_BLOCK, {sig})
            else:
                self._global_original[sig] = self._signal.signal(
                    sig, self._handler
                )
        except (KeyError, KeyboardInterrupt, InterruptedError):
            return

    def _unblock(self, sig: int) -> None:
        """Unblock the specified signal.

        Args:
            sig: The signal to unblock.
        """
        try:
            if self._use_masking:
                self._signal.pthread_sigmask(self._signal.SIG_UNBLOCK, {sig})
            else:
                self._signal.signal(sig, self._global_original.pop(sig))
        except (KeyError, KeyboardInterrupt, InterruptedError):
            return

    def _handler(self, sig: int, _frame: FrameType | None) -> None:
        """Handler for caught signals.

        This method is invoked when the signal is caught during the context.
        It appends the caught signal to the `_global_caught` list.

        Args:
            sig: The signal number.
            _frame: The current stack frame (unused).
        """
        self._global_caught.append(sig)

    @override
    def __enter__(self) -> None:
        """Enter the context and block the specified signals.

        This method blocks the specified signals when entering the context.
        The signals are blocked by increasing the depth of blocking and using
        either `pthread_sigmask` or signal handler overrides, depending on
        the platform.
        """
        if is_main_thread():
            for sig in self.signals:
                depth = self._depth.get(sig, 0)
                self._depth[sig] = depth + 1
                if depth == 0:
                    self._block(sig)

    def _decrement_signal_depth(self) -> None:
        """Decrement the signal depth and unblock when necessary.

        This method reduces the signal blocking depth for each signal. If
        the depth reaches zero, it restores the original signal handler or
        unblocks the signal.
        """
        for sig in self.signals:
            self._depth[sig] -= 1
            if self._depth[sig] == 0:
                del self._depth[sig]
                self._unblock(sig)

    @cached_property
    def _pid(self) -> int:
        """Get the current process ID.

        This property returns the current process ID, which is needed to
        re-emit signals later.

        Returns:
            int: The process ID of the current process.
        """
        return importlib.import_module("os").getpid()

    def _reemit_pending_posix_signals(self) -> None:
        """Re-emit any pending signals on POSIX systems.

        This method checks for any signals that are pending and re-emits them
        using `os.kill`. It ensures that no signals are lost during the
        context.
        """
        pending = self._signal.sigpending()
        os = importlib.import_module("os")
        for sig in self.signals & pending:
            try:
                os.kill(self._pid, sig)
            except OSError:
                continue

    def _reemit_caught_fallback_signals(self) -> None:
        """Re-emit any caught signals after the context exits.

        This method re-emits all caught signals, ensuring they are handled
        outside of the critical section, using `os.kill` to send the signals.
        """
        os = importlib.import_module("os")
        for sig in self._global_caught:
            try:
                os.kill(self._pid, sig)
            except OSError:
                continue

        self._global_caught.clear()

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context and handle signal re-emission.

        This method is called when exiting the context. It ensures that
        any deferred signals are re-emitted based on the signal depth and
        platform-specific behavior.

        Args:
            exc_type: The type of the exception raised (if any).
            exc_val: The exception value (if any).
            exc_tb: The traceback object (if any).
        """
        if is_main_thread():
            self._decrement_signal_depth()
            if self._use_masking and all(
                self._depth.get(sig, 0) == 0 for sig in self.signals
            ):
                self._reemit_pending_posix_signals()
            elif not self._use_masking and all(
                self._depth.get(sig, 0) == 0 for sig in self.signals
            ):
                self._reemit_caught_fallback_signals()
