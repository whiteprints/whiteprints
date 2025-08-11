# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Callable
from functools import cache, cached_property
from gettext import NullTranslations
from typing import TYPE_CHECKING, Final, Literal

from whiteprints.lazy_import import import_lazy


__all__: Final = ["LazyGettext"]


class LazyGettext:
    """Load and return the gettext translation object.

    This method performs the actual loading of the translation catalog
    from the locale directory, based on the configured domain and fallback
    behavior.

    Returns:
        A gettext.NullTranslations instance (or subclass).
    """

    def __init__(
        self,
        locale_directory: str | None = None,
        *,
        fallback: bool = True,
        domain: str = __name__,
    ) -> None:
        """Initializes the LazyGettext instance.

        Args:
            locale_directory: locale directory path.
            fallback: use a fallback if translation is not found.
            domain: gettext domain.
        """
        self.locale_directory = locale_directory
        self.fallback = fallback
        self.domain = domain
        self._translation: NullTranslations | None = None

    def load_translation(self) -> NullTranslations:
        """Load and return the gettext translation object.

        This method performs the actual loading of the translation catalog
        from the locale directory, based on the configured domain and
        fallback behavior.

        Returns:
            A gettext.NullTranslations instance (or subclass).
        """
        return import_lazy("gettext").translation(
            self.domain,
            self.locale_directory,
            fallback=self.fallback,
        )

    @cached_property
    def __call__(self) -> Callable[[str], str]:
        """Performs the actual import and binding of gettext translation.

        Returns:
            A callable that translates strings using gettext.
        """
        self._translation = self.load_translation()
        return self._translation.gettext


@cache
def __getattr__(name: Literal["_"]) -> LazyGettext:
    """Lazily load the `_` function for gettext translation.

    This function is used to lazily load and initialize the `LazyGettext`
    translation function when it is first accessed. If the translation system
    has not been initialized yet, this function will initialize it and return
    the translation function.

    Args:
        name: The name of the attribute being accessed. In this case, it
            must be `"_"` for the translation function.

    Returns:
        LazyGettext: The lazy translation function.

    Raises:
        AttributeError: If any other attribute name is accessed.
    """
    if name == "_":
        os = import_lazy("os")
        return LazyGettext(
            import_lazy("os").path.join(os.path.dirname(__file__), "locale")
        )

    raise AttributeError(name)


if TYPE_CHECKING:
    _: LazyGettext
