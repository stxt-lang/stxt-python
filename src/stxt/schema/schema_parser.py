"""SchemaParser: turns the tree of an already parsed ``@stxt.schema`` document into a
:class:`Schema` (``stxt-impl/schema/schema_parser.txt``)."""

from __future__ import annotations

from typing import Optional

from ..core.name_namespace import parse_name_namespace
from ..core.node import InlineNode, Node
from ..core.platform import is_integer, parse_integer
from ..exceptions import RuntimeException, ValidationException
from .child_definition import ChildDefinition
from .node_definition import NodeDefinition
from .schema import SCHEMA_NAMESPACE, Schema
from .types import TypeRegistry


def _inline(node: Node) -> InlineNode:
    # The schema language is written with inline nodes: anything else is not a schema.
    if isinstance(node, InlineNode):
        return node
    raise ValidationException(node.get_line(), "INVALID_SCHEMA",
                              f"Node '{node.get_name()}' must be inline in a schema")


def transform_node_to_schema(node: Node) -> Schema:
    """Turns the root node of a schema document (``Schema (@stxt.schema): <ns>``) into a Schema.

    Raises:
        ValidationException: ``NOT_STXT_SCHEMA``, ``INVALID_SCHEMA``, ``CHILD_NOT_DEFINED`` and
            the errors of the definitions themselves.
    """
    node_name = node.get_canonical_name()
    namespace_schema = node.get_namespace()

    if node_name != "schema" or namespace_schema != SCHEMA_NAMESPACE:
        raise ValidationException(node.get_line(), "NOT_STXT_SCHEMA",
                                  f"Expected schema({SCHEMA_NAMESPACE}) but got {node_name}({namespace_schema})")
    root = _inline(node)

    description: Optional[str] = None
    description_node = root.get_child("description")
    if description_node is not None:
        description = description_node.get_text()

    # The inline value of the root Schema node is the target namespace
    schema = Schema(root.get_value(), root.get_line(), description)

    all_names: list[str] = []
    for n in root.get_children_by_name("node"):
        sch_node = _create_node_definition(n, schema.get_namespace())
        schema.add_node_definition(sch_node)
        all_names.append(sch_node.get_canonical_name())

    # Every Child of the schema's own namespace must refer to a Node declared in this schema
    # (cross-namespace Children are validated in their own schema, not here).
    for sch_node in schema.get_nodes().values():
        for sch_child in sch_node.get_children().values():
            if sch_child.get_namespace() == schema.get_namespace():
                if sch_child.get_canonical_name() not in all_names:
                    raise ValidationException(0, "CHILD_NOT_DEFINED",
                                              f"Child {sch_child.get_canonical_name()} not defined in {schema.get_namespace()}")

    return schema


def _create_node_definition(node: Node, namespace: str) -> NodeDefinition:
    n = _inline(node)

    # The inline value of "Node" is the name of the target node
    name = n.get_value()

    # Default type INLINE when no "Type:" is given
    type_ = "INLINE"
    type_node = n.get_child("type")
    if type_node is not None:
        type_ = type_node.get_text()

    description: Optional[str] = None
    description_node = n.get_child("description")
    if description_node is not None:
        description = description_node.get_text()

    result = NodeDefinition(name, type_, n.get_line(), description)

    children = n.get_child("children")
    if children is not None:
        # Schema error 13.5: Children in a Node whose type does not admit children
        if not TypeRegistry.admits_children(type_):
            raise ValidationException(children.get_line(), "CHILDREN_NOT_ALLOWED_FOR_TYPE",
                                      f"Type {type_} does not allow children (node {name})")
        for child in _inline(children).get_children_by_name("child"):
            _put_child_to_node_definition(result, child, namespace)

    # Allowed values: only valid for the ENUM type
    values = n.get_children_by_name("values")
    if values:
        if type_ != "ENUM":
            raise ValidationException(n.get_line(), "VALUES_ONLY_SUPPORTED_BY_ENUM",
                                      f"Values only supported for type ENUM, not for type {type_}")
        if len(values) > 1:
            raise RuntimeException("INVALID_SIZE_VALUES", f"Unexpected number of values: {len(values)}")

        values = _inline(values[0]).get_children_by_name("value")
        for value in values:
            result.add_value(value.get_text(), value.get_line())

    # An ENUM must declare at least one value
    if type_ == "ENUM" and len(values) == 0:
        raise ValidationException(n.get_line(), "VALUES_EMPTY_FOR_ENUM", "ENUM Type must include values")

    return result


def _put_child_to_node_definition(node_definition: NodeDefinition, child_node: Node, def_namespace: str) -> None:
    child = _inline(child_node)

    # The inline value of "Child" is the name of the child, with an optional namespace in ()
    nn = parse_name_namespace(child.get_value(), def_namespace, child.get_line(), child.get_value())
    name = nn.get_name()
    namespace = nn.get_namespace()

    min_ = _get_integer(child, "min")
    max_ = _get_integer(child, "max")

    # Invalid cardinality when Min > Max (STXT-SCHEMA-SPEC 10 and 13.7)
    if min_ is not None and max_ is not None and min_ > max_:
        raise ValidationException(child.get_line(), "MIN_GREATER_THAN_MAX", f"Min {min_} greater than Max {max_}")

    node_definition.add_child_definition(ChildDefinition(name, namespace, min_, max_, child.get_line()))


def _get_integer(node: InlineNode, child_name: str) -> Optional[int]:
    n = node.get_child(child_name)
    if n is None:
        return None
    if not is_integer(n.get_text()):
        raise ValidationException(node.get_line(), "INVALID_INTEGER", "Integer not valid: " + n.get_text())
    return parse_integer(n.get_text())


__all__ = ["transform_node_to_schema"]
