"""Schema: logical representation of a ``@stxt.schema`` for a target namespace
(``stxt-impl/schema/schema.txt``)."""

from __future__ import annotations

from typing import Optional

from ..core.string_utils import lower_case, normalize_chars
from ..core.validations import validate_namespace_format
from ..exceptions import ValidationException
from .node_definition import NodeDefinition

#: Namespace of the schema language itself.
SCHEMA_NAMESPACE = "@stxt.schema"


class Schema:
    """A set of node definitions indexed by canonical name, for one target namespace. It is
    the result of :func:`transform_node_to_schema` (or of compiling a template)."""

    SCHEMA_NAMESPACE = SCHEMA_NAMESPACE

    def __init__(self, namespace: str, line: int, description: Optional[str]) -> None:
        self._namespace = lower_case(namespace)
        self._description = description
        # Key = canonical name of the node. Preserves insertion order.
        self._nodes: dict[str, NodeDefinition] = {}

        # The target namespace must be a valid namespace ('a.b' minimum, ASCII)
        validate_namespace_format(self._namespace, line)

    def get_namespace(self) -> str:
        return self._namespace

    def get_description(self) -> Optional[str]:
        return self._description

    def get_nodes(self) -> dict[str, NodeDefinition]:
        return self._nodes

    def get_node_definition(self, name: str) -> Optional[NodeDefinition]:
        """Looks up a node definition by name (canonicalized before the lookup)."""
        return self._nodes.get(normalize_chars(name))

    def add_node_definition(self, node_definition: NodeDefinition) -> None:
        """Raises ``NODE_DEF_ALREADY_DEFINED`` when two Node definitions share a canonical name."""
        qname = node_definition.get_canonical_name()
        if qname in self._nodes:
            raise ValidationException(0, "NODE_DEF_ALREADY_DEFINED",
                                      "Exists a previous node definition with: " + qname)
        self._nodes[qname] = node_definition

    def __repr__(self) -> str:
        return f"Schema({self._namespace!r}, {len(self._nodes)} nodes)"
