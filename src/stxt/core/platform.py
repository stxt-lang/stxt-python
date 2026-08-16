"""Platform utilities: the functions of ``stxt-impl/core/platform.txt`` on Python."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Optional
from urllib.parse import SplitResult, urlsplit

_LINE_BREAK = re.compile(r"\r\n|\n")
_INTEGER = re.compile(r"[-+]?[0-9]+")
_NATURAL = re.compile(r"[0-9]+")


def split_lines(text: str) -> list[str]:
    """Splits the content into lines, accepting both LF and CRLF as line breaks.

    The part after the last break is a line too, possibly empty:
    ``"a\\r\\nb\\n"`` gives ``["a", "b", ""]``.
    """
    return _LINE_BREAK.split(text)


def is_integer(text: str) -> bool:
    """True if ``text`` is a valid integer (sign allowed, ASCII digits only)."""
    return _INTEGER.fullmatch(text) is not None


def is_natural(text: str) -> bool:
    """True if ``text`` is a non-negative integer with no sign and no trailing text."""
    return _NATURAL.fullmatch(text) is not None


def parse_integer(text: str) -> int:
    """Converts ``text`` into an int. Only call it when :func:`is_integer` is true."""
    return int(text)


def parse_uri(text: str) -> Optional[SplitResult]:
    """Parses a URI; ``None`` when it is not valid.

    The result exposes ``scheme`` and ``hostname`` (both empty/None when absent).
    """
    try:
        parts = urlsplit(text)
        # Force the lazy hostname parsing so an invalid netloc surfaces here
        parts.hostname  # noqa: B018
        parts.port  # noqa: B018
        return parts
    except ValueError:
        return None


def is_valid_base64(text: str) -> bool:
    """True if ``text`` is decodable Base64 content.

    Missing padding is tolerated (as the JS and Java ports do), but the content must
    re-encode to itself: partially valid strings with leftover bits are rejected.
    """
    stripped = text.rstrip("=")
    padded = stripped + "=" * (-len(stripped) % 4)
    try:
        decoded = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return False
    reencoded = base64.b64encode(decoded).decode("ascii").rstrip("=")
    return reencoded == stripped
