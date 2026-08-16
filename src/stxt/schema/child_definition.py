"""ChildDefinition: declaration of an expected child inside a Node (``Child:``)
(``stxt-impl/schema/child_definition.txt``)."""

from __future__ import annotations

from typing import Optional

from ..core.string_utils import compact_spaces, is_empty, lower_case, normalize_chars
from ..core.validations import is_valid_node_name, validate_namespace_format
from ..exceptions import ValidationException


class ChildDefinition:
    """The logical pair (canonical name + effective namespace) of an expected child and its
    min/max cardinality. ``min``/``max`` are optional: ``None`` means "no limit set"."""

    def __init__(self, name: str, namespace: Optional[str], min: Optional[int],  # noqa: A002
                 max: Optional[int], line: int) -> None:  # noqa: A002
        self._name = compact_spaces(name)
        self._canonical_name = normalize_chars(name)
        self._namespace = lower_case(namespace)
        self._min = min
        self._max = max

        # The namespace of the child (inherited or explicit) must be valid
        validate_namespace_format(self._namespace, line)

        # A Child name is a node name too: same full STXT name rules as the core parser
        if not is_valid_node_name(self._name):
            raise ValidationException(line, "INVALID_NODE_NAME", "Node name not valid: " + self._name)

    def get_name(self) -> str:
        return self._name

    def get_canonical_name(self) -> str:
        return self._canonical_name

    def get_namespace(self) -> str:
        return self._namespace

    def get_min(self) -> Optional[int]:
        return self._min

    def get_max(self) -> Optional[int]:
        return self._max

    def get_qualified_name(self) -> str:
        """Logical identity of the child: ``namespace:canonical_name``, or just the canonical
        name if there is no namespace. The key in :meth:`NodeDefinition.get_children`."""
        if is_empty(self._namespace):
            return self._canonical_name
        return f"{self._namespace}:{self._canonical_name}"

    def __repr__(self) -> str:
        return f"ChildDefinition({self.get_qualified_name()!r}, min={self._min}, max={self._max})"
