"""DefinitionCompiler: the one pipeline every definition loader shares
(``stxt-impl/schema/definition_compiler.txt``), whatever the store: the in-memory
providers (a document each), :class:`~stxt.runtime.unified_schema_provider.UnifiedSchemaProvider`
(several roots per file) and discovery.

A definition node is validated against the meta-schema of its kind (``@stxt.schema`` or
``@stxt.template``) and, only when valid, transformed into a Schema; a definition that does
not validate is never registered anywhere -- the first validation finding is raised instead.
Everything that changes between the two kinds arrives as a parameter (the meta provider, the
transform function, the error code), so a policy change here reaches every loader.
"""

from __future__ import annotations

from typing import Callable

from ..core.node import Node
from ..core.parser import Parser
from ..exceptions import ParseException, ValidationException
from .schema import Schema
from .schema_provider import SchemaProvider
from .schema_validator import SchemaValidator


def compile_node(node: Node, meta: SchemaProvider, transform: Callable[[Node], Schema]) -> Schema:
    """Validates one root node against the meta provider of its kind and compiles it into
    a :class:`Schema`.

    Args:
        node: root node of the definition (``Schema (@stxt.schema)`` or ``Template (@stxt.template)``).
        meta: provider of the meta-schema of the kind.
        transform: function that turns the validated node into a Schema.

    Raises:
        ValidationException: the first validation finding, if the node does not validate.
    """
    errors = SchemaValidator(meta, True).validate(node)
    if errors:
        raise errors[0]

    return transform(node)


def compile_document(text: str, meta: SchemaProvider, transform: Callable[[Node], Schema],
                     multiple_roots_code: str, kind: str) -> Schema:
    """Parses a whole document that must hold exactly one definition, and compiles it.

    Args:
        text: text of the definition document.
        meta: provider of the meta-schema of the kind.
        transform: function that turns the validated root into a Schema.
        multiple_roots_code: error code when the document does not hold exactly one root
            (``SCHEMA_MULTIPLE_ROOTS`` for schemas, ``TEMPLATE_MULTIPLE_ROOTS`` for templates).
        kind: word naming the kind in the error message (``schema`` or ``template``).

    Raises:
        ParseException: if the document does not parse.
        ValidationException: if the document is not exactly one valid definition.
    """
    nodes = Parser().parse(text)
    if len(nodes) != 1:
        raise ValidationException(ParseException.NO_LINE, multiple_roots_code,
                                  f"A {kind} document must hold exactly 1 root node, got {len(nodes)}")

    return compile_node(nodes[0], meta, transform)


__all__ = ["compile_node", "compile_document"]
