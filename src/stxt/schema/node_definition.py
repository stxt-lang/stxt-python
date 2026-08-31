"""NodeDefinition: definition of a node inside a schema, one ``Node:`` entry
(``stxt-impl/schema/node_definition.txt``)."""

from __future__ import annotations

from typing import Optional

from ..core.string_utils import compact_spaces, normalize_chars, trim_to_not_null
from ..core.validations import is_valid_node_name
from ..exceptions import ParseException, ValidationException
from .child_definition import ChildDefinition


class NodeDefinition:
    """Holds the value type, the expected children (:class:`ChildDefinition`), the optional
    description and, for ENUM, the allowed values."""

    def __init__(self, name: str, type: str, line: int, description: Optional[str]) -> None:  # noqa: A002
        self._name = compact_spaces(name)
        self._canonical_name = normalize_chars(name)
        self._type = type
        self._description = description
        # Key = qualified name of the child (namespace:canonical_name); insertion order
        self._children: dict[str, ChildDefinition] = {}
        # Allowed values for the ENUM type. Set semantics: no duplicates.
        self._values: list[str] = []

        # The inline value of Schema/Node must itself be a valid STXT node name (7.1)
        if not is_valid_node_name(self._name):
            raise ValidationException(line, "INVALID_NODE_NAME", "Node name not valid: " + self._name)

    def get_name(self) -> str:
        return self._name

    def get_canonical_name(self) -> str:
        return self._canonical_name

    def get_type(self) -> str:
        return self._type

    def get_description(self) -> Optional[str]:
        return self._description

    def set_description(self, description: Optional[str]) -> None:
        """Sets the optional description (used by the template ``Description >>`` block)."""
        self._description = description

    def get_children(self) -> dict[str, ChildDefinition]:
        """The declared children, keyed by qualified name, in declaration order."""
        return self._children

    def add_child_definition(self, child_definition: ChildDefinition) -> None:
        """Raises ``CHILD_DUPLICATED`` for two equivalent Child entries."""
        qname = child_definition.get_qualified_name()
        if qname in self._children:
            raise ValidationException(ParseException.NO_LINE, "CHILD_DUPLICATED",
                                      "A child declaration with the same name already exists: " + qname)
        self._children[qname] = child_definition

    def add_value(self, value: str, line: int) -> None:
        """Adds an allowed value (ENUM). Duplicated values (after trim) are ``VALUE_DUPLICATED``."""
        value = trim_to_not_null(value)
        if value in self._values:
            raise ValidationException(line, "VALUE_DUPLICATED", f"The value {value} is duplicated")
        self._values.append(value)

    def is_allowed_value(self, value: str) -> bool:
        """True if no restricted values are defined, or if the value is among the allowed ones."""
        if not self._values:
            return True
        return value in self._values

    def get_values(self) -> list[str]:
        return self._values

    def __repr__(self) -> str:
        return f"NodeDefinition({self._name!r}, {self._type})"
