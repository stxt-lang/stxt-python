"""Namespace and node-name validation (``stxt-impl/core/validations.txt``)."""

from __future__ import annotations

import unicodedata
from typing import Optional

from ..exceptions import ParseException
from .string_utils import compact_spaces, is_empty, normalize_chars, normalize_nfc

# Characters of a namespace label (STXT-SPEC section 7): lower-case ASCII letters and digits
_LABEL_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789")


def is_valid_namespace_format(namespace: str) -> bool:
    """Format of a logical namespace (STXT-SPEC section 7): lower-case ASCII letters, digits
    and dots; an optional leading ``@`` for the reserved namespaces; two or more labels
    ``[a-z0-9]+`` separated by ``.``.

    Checked by a hand-written scan rather than the regex ``^@?[a-z0-9]+(\\.[a-z0-9]+)+$``,
    which in engines that implement a repeated group by recursion (Java) overflowed the stack
    with ~2 000 labels; the scan is linear and identical in every port."""
    n = len(namespace)
    i = 1 if namespace.startswith("@") else 0
    labels = 0
    while True:
        start = i
        while i < n and namespace[i] in _LABEL_CHARS:
            i += 1
        if i == start:
            return False  # empty label: "", "@", "a.", ".a", "a..b"
        labels += 1
        if i == n:
            return labels >= 2
        if namespace[i] != ".":
            return False
        i += 1

_NAME_SEPARATORS = frozenset("-_ ")


_MARK_CATEGORIES = frozenset(("Mn", "Mc"))


def _is_letter_or_digit(char: str) -> bool:
    category = unicodedata.category(char)
    return category.startswith("L") or category == "Nd"


def _is_name_char(char: str) -> bool:
    # STXT-SPEC sections 4.2 / 4.3: Unicode letters (\p{L}), decimal digits (\p{Nd}) and
    # combining marks (\p{Mn}, \p{Mc}) plus the three ASCII separators. Python's `re` has no
    # \p{...}: use the Unicode database.
    if char in _NAME_SEPARATORS:
        return True
    return _is_letter_or_digit(char) or unicodedata.category(char) in _MARK_CATEGORIES


def is_valid_node_name(name: Optional[str]) -> bool:
    """Checks whether a logical node name is valid in a document, schema or template.

    The character check is deliberately made AFTER NFC: the decomposed spelling ``e`` +
    combining acute is a valid spelling of ``é`` and must not be rejected before
    canonicalization. The caller decides whether the resulting error is syntactic
    (:class:`ParseException`) or semantic (:class:`ValidationException`).
    """
    if name is None:
        return False
    nfc_name = normalize_nfc(compact_spaces(name))
    if not nfc_name or not all(_is_name_char(c) for c in nfc_name):
        return False
    # At least one letter or digit (4.2): a string made only of separators ("___") or only
    # of combining marks has no logical name.
    return any(_is_letter_or_digit(c) for c in nfc_name)


def validate_namespace_format(namespace: Optional[str], line_number: int) -> None:
    """Validates the format of an already lower-cased namespace.

    An empty or ``None`` namespace is ignored (nodes without namespace are legal).

    Raises:
        ParseException: ``INVALID_NAMESPACE`` when the format is not valid.
    """
    if namespace is None or namespace == "":
        return
    if not is_valid_namespace_format(namespace):
        raise ParseException(line_number, "INVALID_NAMESPACE", "Namespace not valid: " + namespace)
