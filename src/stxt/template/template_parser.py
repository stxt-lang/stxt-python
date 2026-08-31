"""TemplateParser: turns a ``@stxt.template`` document into an equivalent Schema
(``stxt-impl/template/template_parser.txt``).

A template is syntactic sugar over a schema (STXT-TEMPLATE-SPEC 13): the ``Structure >>`` block
is, itself, an STXT document; it is re-parsed and walked depth first, producing one node
definition per local line and one Child per child line. Errors raised while working on the
re-parsed block are re-raised with the line shifted by the block offset, so they point at the
real line of the original document.
"""

from __future__ import annotations

from typing import Optional

from ..core.node import InlineNode, Node
from ..core.parser import Parser
from ..core.string_utils import is_empty, lower_case, normalize_chars, trim
from ..core.validations import NAMESPACE_FORMAT
from ..exceptions import ParseException, ValidationException
from ..schema.child_definition import ChildDefinition
from ..schema.node_definition import NodeDefinition
from ..schema.schema import Schema
from ..schema.types import TypeRegistry
from .child_line import ChildLine
from .child_line_parser import parse_child_line

# The namespace of the template language itself (re-exported by template_schema_provider);
# the canonical constant is Schema.TEMPLATE_NAMESPACE.
TEMPLATE_NAMESPACE = Schema.TEMPLATE_NAMESPACE


def transform_template_node_to_schema(node: Node) -> Schema:
    """Turns the root node ``Template (@stxt.template): <ns>`` into a Schema.

    Raises:
        ValidationException: ``TEMPLATE_ROOT_NOT_VALID``, ``TEMPLATE_NAMESPACE_EMPTY``,
            ``TEMPLATE_STRUCTURE_REQUIRED`` and every template error, with the line pointing
            at the original document.
    """
    # The root must be 'Template (@stxt.template): <ns>' (STXT-TEMPLATE-SPEC 14.1)
    if node.get_canonical_name() != "template" or node.get_namespace() != TEMPLATE_NAMESPACE:
        raise ValidationException(node.get_line(), "TEMPLATE_ROOT_NOT_VALID",
                                  f"Expected template({TEMPLATE_NAMESPACE}) but got "
                                  f"{node.get_canonical_name()}({node.get_namespace()})")

    # The inline value of "Template" is the target namespace: present and well formed
    target = lower_case(node.get_text())
    if is_empty(target):
        raise ValidationException(node.get_line(), "TEMPLATE_NAMESPACE_EMPTY", "Template namespace is empty")
    if NAMESPACE_FORMAT.fullmatch(target) is None:
        raise ValidationException(node.get_line(), "TEMPLATE_ROOT_NOT_VALID",
                                  f"Template namespace not valid: {node.get_text()}")
    result = Schema(target, node.get_line(), None)

    # Locate the mandatory "Structure >>" block (a text root has no children, hence none)
    structure: Optional[Node] = None
    if isinstance(node, InlineNode):
        structure = node.get_child("structure")
    if structure is None:
        raise ValidationException(node.get_line(), "TEMPLATE_STRUCTURE_REQUIRED", "Template must define 'Structure >>'")

    # The text of the block is an STXT document: re-parse it.
    text = structure.get_text()
    offset = structure.get_line()

    try:
        for n in Parser().parse(text):
            _add_to_schema(result, n)
    except ParseException as pe:
        # Re-raise with the line shifted to the one of the original document, preserving
        # the subtype (ValidationException) so the severity is not downgraded.
        raise pe.with_line(pe.get_line() + offset) from None

    # Optional "Description >>" block: descriptions for the defined nodes (12)
    assert isinstance(node, InlineNode)
    description = node.get_child("description")
    if description is not None:
        try:
            _add_descriptions(result, Parser().parse(description.get_text()))
        except ParseException as pe:
            raise pe.with_line(pe.get_line() + description.get_line()) from None

    return result


def _add_to_schema(schema: Schema, node: Node) -> None:
    # Adds to the schema the definition a Structure node declares, along with its children.
    #
    # Only the orchestration lives here; each of the three shapes a Structure line can take
    # has its own helper below:
    #   * a node of an external namespace  -> _validate_external_node() and nothing is created
    #   * a name seen for the first time   -> _create_definition()
    #   * a reappearance                   -> _validate_reference() and nothing is created
    # and the children of a definition are declared and recursed by _add_children().

    # A Structure line belongs to the template grammar: it must use ':'; a core BLOCK node
    # ('>>') is invalid here even when its text happens to be empty (6.3).
    if not isinstance(node, InlineNode):
        raise ValidationException(node.get_line(), "STRUCTURE_LINE_NOT_VALID", "Template Structure lines must use ':'")

    # Parse the RuleSpec (cardinality / type / values) from the inline value
    cl = parse_child_line(node.get_value(), node.get_line())

    # No explicit namespace => the target namespace of the template
    namespace = node.get_namespace()
    if is_empty(namespace):
        namespace = schema.get_namespace()

    if namespace != schema.get_namespace():
        _validate_external_node(node, cl)
        return  # no definitions are created for nodes of other namespaces

    # New definition or a reappearance (reference)?
    schema_node = schema.get_node_definition(node.get_name())

    if schema_node is not None:
        _validate_reference(node, cl)
        return  # valid reference: nothing is redefined, no children are processed

    schema_node = _create_definition(schema, node, cl)
    _add_children(schema, schema_node, node)


def _validate_external_node(node: InlineNode, cl: ChildLine) -> None:
    # Cross-namespace node (6.4, 10 and 14.15): NOT defined locally; it may only declare
    # cardinality — no type, no ENUM values and no children.
    type_ = cl.get_type()
    if type_ is not None and trim(type_) != "":
        raise ValidationException(node.get_line(), "TYPE_NOT_ALLOWED_IN_EXTERNAL_NAMESPACE",
                                  "Not allowed type definition in external namespaces")

    if cl.get_values() is not None:
        raise ValidationException(node.get_line(), "VALUES_NOT_ALLOWED_IN_EXTERNAL_NAMESPACE",
                                  f"Not allowed values in external namespaces (node {node.get_name()})")

    if len(node.get_children()) > 0:
        raise ValidationException(node.get_line(), "CHILDREN_NOT_ALLOWED_IN_EXTERNAL_NAMESPACE",
                                  f"Not allowed children in external namespaces (node {node.get_name()})")


def _create_definition(schema: Schema, node: InlineNode, cl: ChildLine) -> NodeDefinition:
    # First appearance of a name: creates its NodeDefinition (with its type and its ENUM
    # values, when it has them) and registers it in the schema.
    type_ = cl.get_type()
    if type_ is None:
        type_ = "INLINE"

    # A "@" here means a reference that resolved to nothing: the schema already holds
    # both the previous (closed) definitions and the open ancestors (6.4 and 14.11).
    if type_.startswith("@"):
        raise ValidationException(node.get_line(), "REFERENCE_NOT_FOUND",
                                  f"Reference '{type_}' does not point to a previous definition or an open ancestor")

    schema_node = NodeDefinition(node.get_name(), type_, node.get_line(), None)
    schema.add_node_definition(schema_node)

    if TypeRegistry.get(type_) is None:
        raise ValidationException(node.get_line(), "TYPE_NOT_VALID", "Type not valid: " + type_)

    # ENUM values, if any
    values = cl.get_values()
    if values is not None:
        if type_ != "ENUM":
            # Same code as SchemaParser: a template is sugar equivalent to a schema
            raise ValidationException(node.get_line(), "VALUES_NOT_ALLOWED_FOR_TYPE",
                                      f"Values only supported for type ENUM, not for type {type_}")
        for value in values:
            schema_node.add_value(value, node.get_line())

    # An ENUM with no list of values is an invalid template (9 and 13.7)
    if type_ == "ENUM" and (values is None or len(values) == 0):
        raise ValidationException(node.get_line(), "VALUES_REQUIRED", "ENUM Type must include values")

    return schema_node


def _validate_reference(node: InlineNode, cl: ChildLine) -> None:
    # Reappearance of an already defined name: it must be a "@Node Name" reference, and a
    # reference may override the cardinality but may redefine neither the ENUM values nor
    # the children (6.4, 14.12 and 14.13).
    type_ = cl.get_type()

    # A reappearance without "@" would redefine an existing node: error.
    if type_ is None or not type_.startswith("@"):
        raise ValidationException(node.get_line(), "REFERENCE_REQUIRED",
                                  "Multiple node reference must start with @: " + node.get_name())

    reference = trim(type_[1:])

    # Reference and explicit type on the same line (14.13)
    explicit_type = _reference_type(reference, node.get_canonical_name())
    if explicit_type is not None:
        raise ValidationException(node.get_line(), "REFERENCE_WITH_TYPE_NOT_ALLOWED",
                                  f"Reference '@{node.get_name()}' can not declare a type: {explicit_type}")

    # The name of the reference must match (canonically) the one of the line (14.12)
    if normalize_chars(reference) != node.get_canonical_name():
        raise ValidationException(node.get_line(), "REFERENCE_NAME_NOT_VALID",
                                  f"Reference must be '@{node.get_name()}', not '{reference}'")

    if cl.get_values() is not None:
        raise ValidationException(node.get_line(), "VALUES_NOT_ALLOWED_IN_REFERENCE",
                                  f"Reference '@{node.get_name()}' can not redefine ENUM values")

    if len(node.get_children()) > 0:
        raise ValidationException(node.get_line(), "CHILDREN_NOT_ALLOWED_IN_REFERENCE",
                                  f"Reference '@{node.get_name()}' can not redefine children")


def _add_children(schema: Schema, schema_node: NodeDefinition, node: InlineNode) -> None:
    # Declares every direct child of a definition as a Child (with its cardinality) and
    # recurses into each one as a definition/reference of its own.
    children = node.get_children()

    # Template error 14.9: children under an effective type that does not admit them
    if len(children) > 0 and not TypeRegistry.admits_children(schema_node.get_type()):
        raise ValidationException(node.get_line(), "CHILDREN_NOT_ALLOWED_FOR_TYPE",
                                  f"Type {schema_node.get_type()} does not allow children (node {node.get_name()})")

    for child in children:
        # 6.3 again: every Structure line uses ':', so a child is inline too
        if not isinstance(child, InlineNode):
            raise ValidationException(child.get_line(), "STRUCTURE_LINE_NOT_VALID", "Template Structure lines must use ':'")
        child_cl = parse_child_line(child.get_value(), child.get_line())

        child_namespace = child.get_namespace()
        if is_empty(child_namespace):
            child_namespace = schema.get_namespace()

        # The child is declared as a Child (with its cardinality) in the current definition
        schema_node.add_child_definition(
            ChildDefinition(child.get_name(), child_namespace, child_cl.get_min(), child_cl.get_max(), child.get_line()))

        # And processed recursively as a definition/reference
        _add_to_schema(schema, child)


def _reference_type(reference: str, normalized_name: str) -> Optional[str]:
    # Tells "@Node Name TYPE" (reference + type, 14.13) apart from "@Another Name" (14.12).
    # If the last token is a known type and what comes before it is the name of the node
    # itself, the line is declaring both things.
    cut = reference.rfind(" ")
    if cut < 0:
        return None
    candidate = trim(reference[cut + 1:])
    rest = reference[:cut]
    if TypeRegistry.get(candidate) is not None and normalize_chars(rest) == normalized_name:
        return candidate
    return None


def _add_descriptions(schema: Schema, nodes: list[Node]) -> None:
    # Attaches to the node definitions the descriptions declared in "Description >>" (12):
    # one "Node Name: description" (or a block) per described node.
    for node in nodes:
        namespace = node.get_namespace()
        if is_empty(namespace):
            namespace = schema.get_namespace()

        if namespace != schema.get_namespace():
            raise ValidationException(node.get_line(), "DESCRIPTION_NOT_ALLOWED_IN_EXTERNAL_NAMESPACE",
                                      "Not allowed description in external namespaces")

        if isinstance(node, InlineNode) and len(node.get_children()) > 0:
            raise ValidationException(node.get_line(), "DESCRIPTION_CHILDREN_NOT_ALLOWED",
                                      "Not allowed children in description")

        node_def = schema.get_node_definition(node.get_name())
        if node_def is None:
            raise ValidationException(node.get_line(), "DESCRIPTION_NODE_NOT_FOUND", "Not found node with name: " + node.get_name())

        if node_def.get_description() is not None:
            raise ValidationException(node.get_line(), "DESCRIPTION_DUPLICATED",
                                      "Exists a previous description for node: " + node.get_name())

        node_def.set_description(node.get_text())


__all__ = ["transform_template_node_to_schema"]
