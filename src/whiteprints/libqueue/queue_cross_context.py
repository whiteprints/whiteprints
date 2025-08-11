# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Callable
from types import TracebackType
from typing import (
    Any,
    final,
    override,
)

from whiteprints.libqueue.queue_interface import (
    ConditionLike,
    CrossContext,
    LockLike,
    SemaphoreLike,
)


__all__ = [
    "CrossConditionContext",
    "CrossSemaphoreContext",
    "NoSemaphore",
    "TrueCondition",
]


@final
class TrueCondition(ConditionLike):

    __slots__ = ("acquire", "release")

    @override
    def __init__(self, lock: LockLike) -> None:
        self.acquire = lock.acquire
        self.release = lock.release

    @override
    def __enter__(self) -> None:
        self.acquire()

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
        /,
    ) -> None:
        self.release()

    @override
    def wait(self, timeout: float | None = None) -> None:
        return

    @override
    def wait_for(
        self,
        predicate: Callable[[], bool],
        timeout: float | None = None,
    ) -> bool:
        return True

    @override
    def notify(self, n: int = 1) -> None:
        return

    @override
    def notify_all(self) -> None:
        return


@final
class NoSemaphore(SemaphoreLike):

    __slots__ = ()

    @override
    def __init__(self, value: int = 1) -> None:
        return

    @override
    def acquire(self, /, *args: Any, **kwargs: Any) -> bool:
        return True

    @override
    def release(self) -> None:
        return

    @override
    def __enter__(self) -> None:
        return

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
        /,
    ) -> None:
        return


@final
class CrossSemaphoreContext(CrossContext):
    """Semaphore cross context with split success/exception exits."""

    __slots__ = (
        "__enter__",
        "__exit__",
        "acquire",
        "exit_except",
        "exit_noexcept",
        "release",
        "rollback_on_error",
    )

    @override
    def __init__(
        self,
        acquire: SemaphoreLike,
        release: SemaphoreLike,
        *,
        rollback_on_error: bool = False,
    ) -> None:
        """Bind input/output semaphores and exit strategies.

        Args:
            acquire: Semaphore acquired on entry.
            release: Semaphore released on success.
            rollback_on_error: Re-acquire input on exception if True.
        """
        # hot-path direct binds
        self.acquire = acquire.acquire
        self.release = release.release
        self.rollback_on_error = rollback_on_error

        # context manager entry is the input semaphore's enter
        self.__enter__ = acquire.__enter__

        # success-path exit (used by your try/except/else fast path)
        self.exit_noexcept = self.release

        # exception-path exit (used by your fast path's except block)
        if rollback_on_error:
            self.exit_except = self._exit_except_rollback
            self.__exit__ = self._exit_except_rollback
        else:
            self.exit_except = self._exit_except
            self.__exit__ = self._exit_except

    def _exit_except(
        self,
        exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
        /,
    ) -> None:
        """Exception path without rollback (no-op)."""
        if exc_type is None:
            self.release()

    def _exit_except_rollback(
        self,
        exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
        /,
    ) -> None:
        """Exception path with rollback: re-acquire input."""
        if exc_type is None:
            self.release()
        else:
            self.acquire()


@final
class CrossConditionContext(CrossContext):
    """Final context manager for coordinating two semaphores.

    Acquires one semaphore on enter, releases another on exit.
    Supports rollback (re-acquire) if an error occurs inside the context.

    Attributes:
        acquire(): Manually acquire the input semaphore.
        release(): Manually release the output semaphore.
    """

    __slots__ = (
        "__enter__",
        "__exit__",
        "_acquire",
        "_acquire_lock",
        "_notify",
        "_release",
        "_release_lock",
        "_wait",
        "acquire",
        "exit_except",
        "exit_noexcept",
        "predicate",
        "release",
        "rollback_on_error",
    )

    @override
    def __init__(
        self,
        acquire: ConditionLike,
        release: ConditionLike,
        predicate: Callable[[], bool],
        *,
        rollback_on_error: bool = False,
    ) -> None:
        self._acquire_lock = acquire
        self._acquire = acquire.acquire
        self._release_lock = release
        self._release = acquire.release
        self._notify = release.notify
        self._wait = acquire.wait
        self.predicate = predicate
        self.rollback_on_error = rollback_on_error
        if isinstance(acquire, TrueCondition):
            self.acquire = acquire.acquire
            self.__enter__ = acquire.acquire
        else:
            self.acquire = self._acquire_wait
            self.__enter__ = self._acquire_wait

        if isinstance(release, TrueCondition):
            self.release = acquire.release
            self.exit_noexcept = acquire.release
            self.exit_except = self._exit_except
            self.__exit__ = self._exit_except
        else:
            self.release = acquire.release  # <-- direct bind, no wrapper
            self.exit_noexcept = self._exit_notify_noexcept
            if self.rollback_on_error:
                self.exit_except = self._exit_except  # no notify, rollback
                self.__exit__ = self._exit_except
            else:
                self.exit_except = self._exit_notify_except
                self.__exit__ = self._exit_notify_except

    def _acquire_wait(self, /, *args: Any, **kwargs: Any) -> bool:
        """Acquires the lock.

        Args:
            args: acquire args to forward.
            kwargs: acquire kwargs to forward.

        Returns:
            True if the lock was acquired, False otherwise.
        """
        acquired = self._acquire(*args, **kwargs)
        while acquired and self.predicate():
            self._wait()

        return acquired

    def _exit_notify_noexcept(self) -> None:
        self._notify()
        self._release()

    def _exit_except(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
        /
    ) -> None:
        self._release()

    def _exit_notify_except(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
        /
    ) -> None:
        self._notify()
        self._release()
