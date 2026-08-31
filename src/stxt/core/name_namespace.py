"""NameNamespace: the (name, namespace) pair of the text that precedes ``:`` or ``>>``
(``stxt-impl/core/name_namespace.txt``)."""

from __future__ import annotations

from typing import Optional

from ..exceptions import ParseException
from .constants import EMPTY_NAMESPACE
from .string_utils import lower_case, trim


class NameNamespace:
    """The name and the (lower-cased) namespace read from a node line."""

    __slots__ = ("_name", "_namespace")

    def __init__(self, name: str, namespace: str) -> None:
        self._name = name
        self._namespace = namespace

    def get_name(self) -> str:
        return self._name

    def get_namespace(self) -> str:
        return self._namespace

    def __repr__(self) -> str:
        return f"NameNamespace({self._name!r}, {self._namespace!r})"


def parse_name_namespace(raw_name: Optional[str], inherited_namespace: Optional[str],
                         line_number: int, full_line: str) -> NameNamespace:
    """Splits the node name from its optional namespace in parentheses.

    ``raw_name`` is the text before ``:`` or ``>>``: ``"Node name"``,
    ``"Node name (com.example.docs)"``, ``"Node name (@a.special.namespace)"``. The FORMAT of
    the namespace is not validated here (it is, later, when the node is built); this function
    only splits the two parts and lower-cases the namespace.

    Raises:
        ParseException: ``INVALID_LINE`` or ``INVALID_NAMESPACE``.
    """
    if raw_name is None:
        raise ParseException(line_number, "INVALID_LINE", "Line not valid: " + full_line)

    raw_name = trim(raw_name)

    index_open = raw_name.find("(")
    index_close = raw_name.find(")")

    # Default namespace: the one inherited from the parent, or empty if there is none
    namespace = inherited_namespace if inherited_namespace is not None else EMPTY_NAMESPACE

    if index_open != -1 and index_close != -1:
        # Parentheses present: '(' must come before ')' and ')' must be the last character
        if index_open > index_close or index_close != len(raw_name) - 1:
            raise ParseException(line_number, "INVALID_NAMESPACE", "Line not valid: " + full_line)

        name = trim(raw_name[:index_open])

        # NO trim here: the grammar does not allow spaces inside '( )', so "( com.example )"
        # must fail the namespace format validation later.
        namespace = raw_name[index_open + 1:index_close]

        # The empty namespace "()" is not allowed
        if namespace == "":
            raise ParseException(line_number, "INVALID_NAMESPACE", "Line not valid: " + full_line)

    elif index_open == -1 and index_close == -1:
        # No parentheses: the whole text is the name; the inherited namespace stands
        name = raw_name

    else:
        # A single parenthesis (open without close or close without open): invalid
        raise ParseException(line_number, "INVALID_NAMESPACE", "Line not valid: " + full_line)

    return NameNamespace(name, lower_case(namespace))
