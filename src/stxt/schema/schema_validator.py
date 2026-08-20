"""SchemaValidator: validates an STXT node against the schema of its namespace
(``stxt-impl/schema/schema_validator.txt``).

It implements :class:`Validator`, so it can be plugged into the parse (streaming validation)
or run afterwards over the tree. Every method RETURNS the errors found instead of raising.
"""

from __future__ import annotations

from typing import Sequence

from ..core.node import InlineNode, Node
from ..exceptions import ValidationException
from ..processors.validator import Validator
from .child_definition import ChildDefinition
from .node_definition import NodeDefinition
from .schema import Schema
from .schema_provider import SchemaProvider
from .types import TypeRegistry


class SchemaValidator(Validator):
    """Checks: existence of the node in the schema, validity of the value according to its type,
    the closed content model (every child must be declared) and the cardinalities."""

    def __init__(self, schema_provider: SchemaProvider, recursive: bool = False) -> None:
        self._schema_provider = schema_provider
        self._recursive_validation = recursive

    def validate(self, node: Node) -> list[ValidationException]:
        """Validates the node and, optionally, its subtree. ``SCHEMA_NOT_FOUND`` when the
        provider has no schema for the node's namespace. A node with the empty namespace is
        never validated (STXT-SCHEMA-SPEC 5)."""
        errors: list[ValidationException] = []

        namespace = node.get_namespace()

        # The empty namespace is never validated (STXT-SCHEMA-SPEC 5): a node that neither
        # declares nor inherits a namespace is valid by definition, no schema is looked up
        # for it and SCHEMA_NOT_FOUND is never reported for it. Its children are still
        # walked when recursive, because one of them may declare a namespace of its own.
        if namespace == "":
            if self._recursive_validation and isinstance(node, InlineNode):
                for n in node.get_children():
                    errors.extend(self.validate(n))
            return errors

        sch = self._schema_provider.get_schema(namespace)

        if sch is None:
            errors.append(ValidationException(node.get_line(), "SCHEMA_NOT_FOUND", "Not found schema: " + namespace))
            return errors

        errors.extend(self.validate_against_schema(node, sch))

        # Optional recursive validation of the children (only an InlineNode has any)
        if self._recursive_validation and isinstance(node, InlineNode):
            for n in node.get_children():
                errors.extend(self.validate(n))

        return errors

    def validate_against_schema(self, node: Node, sch: Schema) -> list[ValidationException]:
        """Validates a node against an already resolved schema: existence, value type,
        declared children and cardinalities."""
        errors: list[ValidationException] = []

        schema_node = sch.get_node_definition(node.get_canonical_name())

        # Closed model: the node must be defined in the schema of its namespace
        if schema_node is None:
            errors.append(ValidationException(node.get_line(), "NODE_NOT_EXIST_IN_SCHEMA",
                                              f"NOT EXIST NODE {node.get_canonical_name()} for namespace {sch.get_namespace()}"))
            return errors

        errors.extend(self._validate_value(schema_node, node))
        errors.extend(self._validate_children_declared(schema_node, node))
        errors.extend(self._validate_count(schema_node, node))
        return errors

    @staticmethod
    def _children_of(node: Node) -> Sequence[Node]:
        # The children of a node for the purposes of the content model: a TextNode has none
        if isinstance(node, InlineNode):
            return node.get_children()
        return ()

    def _validate_children_declared(self, ns_node: NodeDefinition, node: Node) -> list[ValidationException]:
        # Closed content model (STXT-SCHEMA-SPEC 6): only the declared direct children are
        # allowed; the error is reported on the line of the offending child.
        errors: list[ValidationException] = []
        declared = ns_node.get_children()
        for child in self._children_of(node):
            if child.get_qualified_name() not in declared:
                errors.append(ValidationException(child.get_line(), "CHILD_NOT_DECLARED",
                                                  f"Child '{child.get_qualified_name()}' not declared in node '{node.get_qualified_name()}'"))
        return errors

    def _validate_value(self, ns_node: NodeDefinition, n: Node) -> list[ValidationException]:
        errors: list[ValidationException] = []
        node_type = ns_node.get_type()

        type_ = TypeRegistry.get(node_type)
        if type_ is None:
            errors.append(ValidationException(n.get_line(), "TYPE_NOT_SUPPORTED", "Node type not supported: " + node_type))
            return errors

        try:
            type_.validate(ns_node, n)
        except ValidationException as ve:
            errors.append(ve)
        except Exception as e:  # noqa: BLE001 - collected, never propagated
            errors.append(ValidationException(n.get_line(), "VALIDATION_ERROR", str(e)))
        return errors

    def _validate_count(self, ns_node: NodeDefinition, node: Node) -> list[ValidationException]:
        # Counts the direct children by qualified name and checks cardinalities. Order
        # independent: it counts occurrences, not positions.
        errors: list[ValidationException] = []
        children_by_name: dict[str, list[Node]] = {}

        for child in self._children_of(node):
            children_by_name.setdefault(child.get_qualified_name(), []).append(child)

        for ch_node in ns_node.get_children().values():
            observed_children = children_by_name.get(ch_node.get_qualified_name(), [])
            errors.extend(self._validate_cardinality(ch_node, len(observed_children), node, observed_children))
        return errors

    @staticmethod
    def _validate_cardinality(ch_node: ChildDefinition, num: int, node: Node,
                              children: list[Node]) -> list[ValidationException]:
        errors: list[ValidationException] = []
        min_ = ch_node.get_min()
        max_ = ch_node.get_max()

        if min_ is not None and num < min_:
            errors.append(ValidationException(node.get_line(), "INVALID_NUMBER",
                                              f"{num} nodes of '{ch_node.get_qualified_name()}' and min is {min_}"))

        if max_ is not None and num > max_:
            # Error on the parent...
            errors.append(ValidationException(node.get_line(), "INVALID_NUMBER",
                                              f"{num} nodes of '{ch_node.get_qualified_name()}' and max is {max_}"))
            # ...and on each offending child, for line-accurate reporting
            for child in children:
                errors.append(ValidationException(child.get_line(), "INVALID_NUMBER",
                                                  f"Too many '{ch_node.get_qualified_name()}' nodes: found {num}, max is {max_}"))
        return errors


__all__ = ["SchemaValidator"]
