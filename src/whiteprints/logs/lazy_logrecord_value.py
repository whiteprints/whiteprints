# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Function serializer with lazy reconstruction for non-picklable objects.

This module provides `LazyRecordValue`, a lightweight wrapper that captures a
function call (function, args, kwargs) and serializes it in a way that survives
Python's inherent limitations around pickling dynamic code, closures, and
module references.

Unlike heavy-duty serializers like `dill` or `cloudpickle`, which attempt to
capture the entire Python object graph (often unsafely and opaquely),
`LazyRecordValue` does not attempt to pickle arbitrary code objects or runtime
environments. Instead, it focuses on **symbolic reconstruction** of the
function and its dependencies using:

- Function bytecode via `marshal` (only for non-builtins)
- Serialized closure cells
- Explicit capture of referenced global names
- Symbolic encoding of modules and importable objects using
  `_ModuleType` and `_NamedImportable`
- Serialization of `__defaults__` and `__kwdefaults__` to preserve argument
  behavior

The deserialization process lazily re-imports what it needs using
`import_lazy()`, ensuring fast startup, better cross-process safety, and
avoidance of runtime introspection failure modes common in `cloudpickle`.

This includes:

- Positional arguments (`args`)
- Keyword arguments (`kwargs`)
- Default values for positional or keyword-only parameters
- Referenced globals (`__globals__`)
- Captured closures (`__closure__`)

**What it avoids:**
- No reliance on runtime monkeypatching
- No VM heap crawling or unsafe bytecode hacks
- No opaque blob serialization of environments

This makes `LazyRecordValue` better suited to deterministic,
multiprocessing-safe, reproducible execution contexts—especially where code
size and startup latency matter.

Limitations:
- Functions relying on runtime-bound locals (e.g. generator frames) are not
  supported.
- Cannot pickle arbitrary bound methods or class scopes that depend on runtime
  state.
"""

from collections.abc import Callable, Iterable, Mapping
from types import BuiltinFunctionType, CellType, FunctionType, ModuleType
from typing import (
    NamedTuple,
    Protocol,
    TypedDict,
    TypeGuard,
    cast,
    runtime_checkable,
)

from whiteprints.lazy_import import import_lazy
from whiteprints.signals_handler import DelaySignals


type LiteralPicklable = (
    int
    | float
    | str
    | bool
    | bytes
    | list[LiteralPicklable]
    | dict[str, LiteralPicklable]
    | tuple[LiteralPicklable, ...]
    | None
)
"""A recursive union type representing values that can be safely pickled
without custom logic.

Includes base literals and containers of such values.
"""


class _NamedImportable(NamedTuple):
    """Represents an importable object by its module and name.

    Attributes:
        module: The fully-qualified module name.
        name: The attribute name within the module.
    """

    module: str
    name: str


type MaybePicklable = LiteralPicklable | ModuleType | NamedImportable | None
"""A value that may or may not be trivially picklable.

Includes modules and importable references which require special handling.
"""


class _ModuleType(NamedTuple):
    """A strictly picklable value supported by `LazyRecordValue`.

    Excludes dynamically defined objects or values requiring context.
    """

    module: str


type Picklable = LiteralPicklable | _ModuleType | _NamedImportable
"""A strictly picklable value supported by `LazyRecordValue`.

Excludes dynamically defined objects or values requiring context.
"""


@runtime_checkable
class NamedImportable(Protocol):
    """Protocol for importable objects with standard import metadata.

    Attributes:
        __module__: The module in which the object is defined.
        __name__: The name of the object in its module.
    """

    __module__: str
    __name__: str


def _is_named_importable(
    value: object,
) -> TypeGuard[ModuleType | NamedImportable]:
    return isinstance(value, ModuleType) or (
        hasattr(value, "__name__") and hasattr(value, "__module__")
    )


class LazyRecordValueState(TypedDict):
    """The serialized state of a `LazyRecordValue` instance.

    Attributes:
        builtin: Whether the function is a built-in.
        module: The module where the function is defined.
        name: The name of the function.
        code: Marshalled bytecode for dynamic functions.
        args: Positional arguments.
        kwargs: Keyword arguments.
        closure: Serialized closure cells.
        extra_globals: Required globals.
    """

    builtin: bool
    module: str
    name: str
    code: bytes
    args: list[Picklable]
    kwargs: dict[str, Picklable]
    defaults: list[Picklable] | None
    kwdefaults: dict[str, Picklable] | None
    closure: list[Picklable] | None
    extra_globals: dict[str, Picklable]


class LazyRecordValue[R]:
    """A serializable wrapper around a function and its arguments.

    This class captures a callable and its arguments, allowing it to be safely
    pickled and later reconstructed — even if the function is dynamically
    defined, contains closures, or references non-picklable objects.

    It supports:
    - Built-in functions
    - Named importables (functions, classes, etc. with __module__ and __name__)
    - User-defined functions with bytecode, closures, and dynamic globals
    - Modules, by storing their import path

    During serialization (`__getstate__`), all non-picklable references are
    identified and converted to symbolic descriptors (`_ModuleType` or
    `_NamedImportable`) so they can be re-imported during unpickling. This
    includes unpicklables found in:

    - `args`: Positional arguments passed to the function
    - `kwargs`: Keyword arguments passed to the function
    - `__defaults__`: Default values for positional-or-keyword parameters
    - `__kwdefaults__`: Default values for keyword-only parameters
    - `__globals__`: Referenced global names used by the function
    - `__closure__`: Captured variables from the function's lexical scope

    These objects are not pickled directly; instead, their identity (module,
    name) is stored, and they are re-imported lazily using `import_lazy` during
    reconstruction (`__setstate__`).

    Attributes:
        function: The original or reconstructed callable.
        args: Function arguments. May contain unpicklable values, which are
            symbolically encoded.
        kwargs: Function keyword arguments. Also serialized with symbolic
            substitution if needed.
    """

    def __init__(
        self,
        function: Callable[..., R],
        *args: MaybePicklable,
        **kwargs: MaybePicklable,
    ) -> None:
        """Initializes the lazy record with a function and its arguments.

        Args:
            function: The callable to wrap.
            *args: Positional arguments (may be partially non-picklable).
            **kwargs: Keyword arguments (may be partially non-picklable).
        """
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def __call__(self) -> R:
        """Invokes the stored function with its arguments.

        Returns:
            The result of the function call.
        """
        return self.function(*self.args, **self.kwargs)

    @staticmethod
    def _make_picklable(element: MaybePicklable) -> Picklable:
        """Converts a possibly non-picklable element into a serializable form.

        Args:
            element: The element to convert.

        Returns:
            A `Picklable` version of the element.
        """
        if isinstance(element, ModuleType):
            return _ModuleType(module=element.__name__)

        if _is_named_importable(element):
            return _NamedImportable(
                module=element.__module__,
                name=element.__name__,
            )

        return cast("LiteralPicklable", element)

    @classmethod
    def _make_picklable_args(
        cls, args: Iterable[MaybePicklable]
    ) -> list[Picklable]:
        """Converts a sequence of arguments to picklable form.

        Args:
            args: The original argument list.

        Returns:
            A picklable list of arguments.
        """
        return [cls._make_picklable(arg) for arg in args]

    @classmethod
    def _make_picklable_kwargs(
        cls, kwargs: Mapping[str, MaybePicklable]
    ) -> dict[str, Picklable]:
        """Converts a dictionary of keyword arguments to picklable form.

        Args:
            kwargs: The original keyword arguments.

        Returns:
            A dictionary of picklable keyword arguments.
        """
        return {
            key: cls._make_picklable(value) for key, value in kwargs.items()
        }

    @classmethod
    def _make_picklable_closure(
        cls, closure: Iterable[CellType] | None
    ) -> list[Picklable] | None:
        """Serializes the contents of a closure if present.

        Args:
            closure: An iterable of cell objects or None.

        Returns:
            A list of picklable cell contents, or None.
        """
        if closure is None:
            return None

        picklable_closure: list[Picklable] = []
        for cell in closure:
            cell_contents = cell.cell_contents
            picklable_closure.append(cls._make_picklable(cell_contents))

        return picklable_closure

    def __getstate__(self) -> LazyRecordValueState:
        """Serializes the `LazyRecordValue` instance into a picklable state.

        Returns:
            A dictionary representing the pickled state.
        """
        with DelaySignals():
            if isinstance(self.function, BuiltinFunctionType):
                return LazyRecordValueState(
                    builtin=True,
                    module=self.function.__module__,
                    name=self.function.__name__,
                    code=b"",
                    args=self._make_picklable_args(self.args),
                    kwargs=self._make_picklable_kwargs(self.kwargs),
                    defaults=None,
                    kwdefaults=None,
                    closure=[],
                    extra_globals={},
                )

            function = import_lazy("inspect").unwrap(self.function)
            function_code = function.__code__
            code = import_lazy("marshal").dumps(function_code)
            picklable_closure = self._make_picklable_closure(
                function.__closure__
            )

            globals_used = (
                set(function_code.co_names)
                - set(function_code.co_freevars)
                - set(function_code.co_cellvars)
            )
            extra_globals = {
                name: self._make_picklable(function.__globals__[name])
                for name in function.__globals__
                if name in globals_used
            }

            defaults = (
                None
                if function.__defaults__ is None
                else self._make_picklable_args(function.__defaults__)
            )
            kwdefaults = (
                None
                if function.__kwdefaults__ is None
                else self._make_picklable_kwargs(function.__kwdefaults__)
            )

            return LazyRecordValueState(
                builtin=False,
                module=self.function.__module__,
                name=self.function.__name__,
                code=code,
                args=self._make_picklable_args(self.args),
                kwargs=self._make_picklable_kwargs(self.kwargs),
                defaults=defaults,
                kwdefaults=kwdefaults,
                closure=picklable_closure,
                extra_globals=extra_globals,
            )

    @staticmethod
    def _make_arg(picklable: Picklable) -> MaybePicklable:
        """Restores a picklable object to its runtime value.

        Args:
            picklable: A pickled representation.

        Returns:
            The live Python object.
        """
        if isinstance(picklable, _ModuleType):
            return import_lazy(picklable.module)

        if isinstance(picklable, _NamedImportable):
            return getattr(import_lazy(picklable.module), picklable.name)

        return picklable

    @staticmethod
    def _make_cell(picklable: object) -> CellType:
        """Wraps an object into a cell (used for closure reconstruction).

        Args:
            picklable: The object to wrap.

        Returns:
            A cell object containing the input.
        """
        if isinstance(picklable, _ModuleType):
            return CellType(import_lazy(picklable.module))

        if isinstance(picklable, _NamedImportable):
            return CellType(
                getattr(import_lazy(picklable.module), picklable.name)
            )

        return CellType(picklable)

    def __setstate__(self, state: LazyRecordValueState) -> None:
        """Restores a `LazyRecordValue` instance from serialized state.

        Args:
            state: A dictionary produced by `__getstate__`.
        """
        with DelaySignals():
            self.args = tuple(self._make_arg(arg) for arg in state["args"])
            self.kwargs = {
                key: self._make_arg(value)
                for key, value in state["kwargs"].items()
            }

            if state["builtin"]:
                mod = import_lazy(state["module"])
                self.function = getattr(mod, state["name"])
            else:
                code = import_lazy("marshal").loads(state["code"])

                defaults = (
                    None
                    if state["defaults"] is None
                    else tuple(self._make_arg(x) for x in state["defaults"])
                )

                kwdefaults = (
                    None
                    if state["kwdefaults"] is None
                    else {
                        k: self._make_arg(v)
                        for k, v in state["kwdefaults"].items()
                    }
                )

                closure_vals = state.get("closure", [])
                namespace: dict[str, MaybePicklable] = {
                    name: self._make_arg(value)
                    for name, value in state.get("extra_globals", {}).items()
                }

                self.function = FunctionType(
                    code,
                    namespace,
                    name=state["name"],
                    closure=(
                        None
                        if closure_vals is None
                        else tuple(
                            self._make_cell(val) for val in closure_vals
                        )
                    ),
                )
                self.function.__defaults__ = defaults
                self.function.__kwdefaults__ = kwdefaults
