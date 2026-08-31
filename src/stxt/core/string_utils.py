"""String utilities (``stxt-impl/core/string_utils.txt``)."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

# STXT-SPEC section 4: a blank is exactly U+0020 or U+0009. Every trim in the core works on
# these two characters only; ``str.strip()`` and ``\s`` are deliberately avoided because they
# also remove NBSP, U+3000, U+2028... which STXT treats as content.
BLANKS = " \t"
_BLANK_RUN = re.compile(r"[ \t]+")
_SEPARATOR_RUN = re.compile(r"[-_ \t]+")


def trim(text: Optional[str]) -> str:
    """Removes leading and trailing blanks (space and tab only); ``""`` for ``None``."""
    return (text or "").strip(BLANKS)


def normalize_nfc(text: str) -> str:
    """Unicode NFC normalization, independent of the current locale."""
    return unicodedata.normalize("NFC", text)


def compact_spaces(text: Optional[str]) -> str:
    """Trim + collapse of every inner run of blanks into a single space. Used for node names."""
    return _BLANK_RUN.sub(" ", trim(text))


def normalize_chars(text: Optional[str]) -> str:
    """Canonical node name (STXT-SPEC section 4.3).

    Trim (blanks only), NFC, lower case, every run of separators (``-``, ``_``, blanks) becomes
    a single ``-``, and leading/trailing ``-`` are removed. Diacritics and non-Latin letters are kept:
    ``"Caña" == "caña"`` but ``"Caña" != "Cana"``.

    May return the empty string (e.g. for ``"___"``): the caller treats that as an error.
    """
    value = trim(text)
    if not value:
        return ""
    value = normalize_nfc(value).lower()
    value = _SEPARATOR_RUN.sub("-", value)
    return value.strip("-")


def lower_case(text: Optional[str]) -> str:
    """Locale-independent lower case; ``""`` for ``None``. Used for namespaces."""
    return (text or "").lower()


def trim_to_not_null(text: Optional[str]) -> str:
    """``""`` for ``None``; otherwise the text trimmed on both sides (blanks only)."""
    return trim(text)


def right_trim(text: Optional[str]) -> str:
    """Removes the trailing blanks (space and tab only) of a line. Used for ``>>`` text block
    lines (STXT-SPEC section 10.2); a trailing NBSP is kept as content."""
    return (text or "").rstrip(BLANKS)


def is_empty(text: Optional[str]) -> bool:
    """True if ``text`` is ``None`` or the empty string."""
    return text is None or text == ""


def remove_utf8_bom(text: str) -> str:
    """Removes the leading UTF-8 BOM if present."""
    return text[1:] if text.startswith("\ufeff") else text


def join(parts: Iterable[str], separator: str) -> str:
    """Joins the strings inserting the separator between them."""
    return separator.join(parts)


def split(text: str, separator: str) -> list[str]:
    """Splits ``text`` by the separator and returns the fragments."""
    return text.split(separator)


def ends_with(text: str, suffix: str) -> bool:
    """True if ``text`` ends with the given suffix."""
    return text.endswith(suffix)


def equals_ignore_case(a: str, b: str) -> bool:
    """Case-insensitive string comparison."""
    return a.lower() == b.lower()
