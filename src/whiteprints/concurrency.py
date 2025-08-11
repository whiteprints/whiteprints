# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib
from typing import Final
from uuid import UUID


__all__: Final = [
    "has_mutated_classvars",
    "is_main_process",
    "is_main_thread",
    "reset_all_mutated_classvars",
    "session_id",
]
"""Public module attributes."""


def is_main_thread() -> bool:
    """Check if the current thread is the main thread.

    This function checks if the current thread is the main thread by comparing
    the current thread with the main thread from the `threading` module.

    Returns:
        bool: True if the current thread is the main thread, False otherwise.
    """
    threading = importlib.import_module("threading")
    return threading.current_thread() is threading.main_thread()


def is_main_process() -> bool:
    """Check if the current process is the main process.

    This function reliably identifies the main process across all
    multiprocessing contexts (`spawn`, `forkserver`, and `fork`), by checking
    the process name against "MainProcess".

    - On `fork` and `spawn`, the main process has the name "MainProcess".
    - On `forkserver`, the main process has the name "MainProcess", but the
      actual main process's PID is different from the `forkserver` process's
      PID, so it still relies on the process name.

    Note:
        Users **should never name any process "MainProcess"**. Naming a
        process this way would cause this function to misidentify child
        processes as the main process. It is strongly discouraged to assign
        custom names like `"MainProcess"` to any process, as it could interfere
        with this functionality and lead to erroneous behavior.

    This is the only **reliable method** to determine the main process,
    especially when using `forkserver`, where `parent_process()` can fail due
    to the nature of process forking.

    Returns:
        bool: True if the current process is the main process, False otherwise.
    """
    multiprocessing = importlib.import_module("multiprocessing")
    current_process = multiprocessing.current_process()
    return current_process.name == "MainProcess"


_MUTATED_CLASSVAR_CLASSES: set[type] = set()


def has_mutated_classvars[T: type](cls: T) -> T:
    """Mark classes with mutated `ClassVar` state that needs resetting.

    This decorator is used to mark classes that have mutated their `ClassVar`
    state, ensuring that their state can be reset when needed.

    Args:
        cls: The class to be decorated.

    Returns:
        The original class, unmodified.
    """
    reset = getattr(cls, "reset_class", None)
    if callable(reset):
        _MUTATED_CLASSVAR_CLASSES.add(cls)

    return cls


def reset_all_mutated_classvars() -> None:
    """Reset the `ClassVar` state for all mutated classes.

    This function resets the `ClassVar` state for all classes that have been
    marked with the `has_mutated_classvars` decorator. It calls each class's
    `reset_class` method to return the class to its original state.
    """
    for cls in _MUTATED_CLASSVAR_CLASSES:
        reset = getattr(cls, "reset_class", lambda: None)
        if callable(reset):
            reset()


def session_id() -> UUID:
    """Get a unique session id and share it thanks to os.environ.

    Returns:
        A unique session id.
    """
    os = importlib.import_module("os")
    sid = os.getenv("__SESSION_ID")
    if sid is not None:
        return UUID(sid)

    new_id = str(importlib.import_module("uuid").uuid4())
    os.environ["__SESSION_ID"] = str(new_id)
    return UUID(new_id)
