"""Platform utilities: the functions of ``stxt-impl/core/platform.txt`` on Python."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Iterator

_LINE_BREAK = re.compile(r"\r\n|\n")
_INTEGER = re.compile(r"[-+]?[0-9]+")
_NATURAL = re.compile(r"[0-9]+")


def split_lines(text: str) -> list[str]:
    """Splits the content into lines, accepting both LF and CRLF as line breaks.

    The part after the last break is a line too, possibly empty:
    ``"a\\r\\nb\\n"`` gives ``["a", "b", ""]``.
    """
    return _LINE_BREAK.split(text)


def iter_lines(text: str) -> Iterator[str]:
    """Iterates the lines of the content lazily, at every LF or CRLF (a lone CR is content,
    STXT-SPEC 3), without the trailing empty line: the final line break terminates the last
    line, so ``"a\\nb\\n"`` and ``"a\\nb"`` both give ``"a"``, ``"b"`` (and ``""`` gives no line).
    The parser consumes it so that no line is materialised before its limits apply."""
    start = 0
    length = len(text)
    while start < length:
        end = text.find("\n", start)
        if end == -1:
            end = length
        cut = end - 1 if end > start and text[end - 1] == "\r" else end
        yield text[start:cut]
        start = end + 1


def is_integer(text: str) -> bool:
    """True if ``text`` is a valid integer (sign allowed, ASCII digits only)."""
    return _INTEGER.fullmatch(text) is not None


def is_natural(text: str) -> bool:
    """True if ``text`` is a non-negative integer with no sign and no trailing text."""
    return _NATURAL.fullmatch(text) is not None


def parse_integer(text: str) -> int:
    """Converts ``text`` into an int. Only call it when :func:`is_integer` is true."""
    return int(text)


def is_valid_base64(text: str) -> bool:
    """True if ``text`` is decodable Base64 content.

    Missing padding is tolerated (as the JS and Java ports do), but the content must
    re-encode to itself: partially valid strings with leftover bits are rejected, and so is
    the empty string (STXT-SCHEMA-SPEC 9.5). ``validate=True`` makes the decoder reject
    characters outside the alphabet instead of silently ignoring them.
    """
    stripped = text.rstrip("=")
    if stripped == "":
        return False
    padded = stripped + "=" * (-len(stripped) % 4)
    # The padding, when present, must be exactly the one that completes the last quartet
    # (stxt-impl platform.txt, point 3): "aGVsbG8==" and "aGVsbG8x=" are not valid.
    if text != stripped and text != padded:
        return False
    try:
        decoded = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return False
    reencoded = base64.b64encode(decoded).decode("ascii").rstrip("=")
    return reencoded == stripped
