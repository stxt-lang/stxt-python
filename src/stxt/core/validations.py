"""Namespace and node-name validation (``stxt-impl/core/validations.txt``)."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from ..exceptions import ParseException
from .string_utils import compact_spaces, is_empty, normalize_chars, normalize_nfc

# Format of a logical namespace (STXT-SPEC section 7): lower-case ASCII letters, digits and
# dots; an optional leading '@' for the reserved namespaces; two or more labels.
NAMESPACE_FORMAT = re.compile(r"@?[a-z0-9]+(\.[a-z0-9]+)+")

_NAME_SEPARATORS = frozenset("-_ ")


def _is_name_char(char: str) -> bool:
    # STXT-SPEC sections 4.2 / 4.3: Unicode letters (\p{L}) and decimal digits (\p{Nd}) plus
    # the three ASCII separators. Python's `re` has no \p{...}: use the Unicode database.
    if char in _NAME_SEPARATORS:
        return True
    category = unicodedata.category(char)
    return category.startswith("L") or category == "Nd"


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
    # A string made only of separators (for example "___") has no logical name.
    return not is_empty(normalize_chars(nfc_name))


def validate_namespace_format(namespace: Optional[str], line_number: int) -> None:
    """Validates the format of an already lower-cased namespace.

    An empty or ``None`` namespace is ignored (nodes without namespace are legal).

    Raises:
        ParseException: ``INVALID_NAMESPACE`` when the format is not valid.
    """
    if namespace is None or namespace == "":
        return
    if NAMESPACE_FORMAT.fullmatch(namespace) is None:
        raise ParseException(line_number, "INVALID_NAMESPACE", "Namespace not valid: " + namespace)
