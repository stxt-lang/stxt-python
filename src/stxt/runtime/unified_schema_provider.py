"""UnifiedSchemaProvider: a provider that handles both schemas and templates (a consumer
convenience, not normative)."""

from __future__ import annotations

from typing import Callable, Optional

from ..core.node import Node
from ..core.parser import Parser
from ..core.string_utils import lower_case
from ..schema.definition_compiler import compile_node
from ..schema.schema import SCHEMA_NAMESPACE, TEMPLATE_NAMESPACE, Schema
from ..schema.schema_parser import transform_node_to_schema
from ..schema.schema_provider import SchemaProvider, SchemaProviderMeta
from ..template.template_parser import transform_template_node_to_schema
from ..template.template_schema_provider import MetaTemplateSchemaProvider


class UnifiedSchemaProvider(SchemaProvider):
    """Detects from the namespace of each root node whether it is a schema (``@stxt.schema``)
    or a template (``@stxt.template``), validates it against its meta-schema and registers the
    resulting Schema. Documents of any other namespace are ignored. Serves the two meta-schemas
    itself."""

    def __init__(self) -> None:
        self._schemas: dict[str, Schema] = {}
        self._schema_meta: SchemaProvider = SchemaProviderMeta()
        self._template_meta: SchemaProvider = MetaTemplateSchemaProvider()

    def get_schema(self, namespace: str) -> Optional[Schema]:
        key = lower_case(namespace)
        if key == TEMPLATE_NAMESPACE:
            return self._template_meta.get_schema(key)
        if key == SCHEMA_NAMESPACE:
            return self._schema_meta.get_schema(key)
        return self._schemas.get(key)

    def add_file(self, text: str) -> None:
        """Parses a document and registers every schema or template it defines.

        Raises:
            ParseException: if the document cannot be parsed.
            ValidationException: the first error of a definition against its meta-schema.
        """
        for node in Parser().parse(text):
            namespace = node.get_namespace()
            if namespace == TEMPLATE_NAMESPACE:
                self._add_node(node, self._template_meta, transform_template_node_to_schema)
            elif namespace == SCHEMA_NAMESPACE:
                self._add_node(node, self._schema_meta, transform_node_to_schema)

    def _add_node(self, node: Node, meta: SchemaProvider, transform: Callable[[Node], Schema]) -> None:
        # Compiles a definition root through the shared pipeline (see definition_compiler)
        # and registers it; a definition that does not validate is never registered.
        schema = compile_node(node, meta, transform)

        self._schemas[lower_case(schema.get_namespace())] = schema

    def clear(self) -> None:
        """Removes every schema and template registered in this provider."""
        self._schemas.clear()

    def get_all_schemas(self) -> list[Schema]:
        """Every schema registered in this provider, in registration order."""
        return list(self._schemas.values())


__all__ = ["UnifiedSchemaProvider"]
