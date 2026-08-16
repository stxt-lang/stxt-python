"""UnifiedSchemaProvider: a provider that handles both schemas and templates (a consumer
convenience, not normative)."""

from __future__ import annotations

from typing import Optional

from ..core.node import Node
from ..core.parser import Parser
from ..core.string_utils import lower_case
from ..exceptions import ValidationException
from ..schema.schema import SCHEMA_NAMESPACE, Schema
from ..schema.schema_parser import transform_node_to_schema
from ..schema.schema_provider import SchemaProvider, SchemaProviderMeta
from ..schema.schema_validator import SchemaValidator
from ..template.template_parser import transform_template_node_to_schema
from ..template.template_schema_provider import TEMPLATE_NAMESPACE, MetaTemplateSchemaProvider


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
        if namespace == TEMPLATE_NAMESPACE:
            return self._template_meta.get_schema(key)
        if namespace == SCHEMA_NAMESPACE:
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
                self._add_template_node(node)
            elif namespace == SCHEMA_NAMESPACE:
                self._add_schema_node(node)

    def _add_template_node(self, node: Node) -> None:
        self._throw_if_invalid(SchemaValidator(self._template_meta, True).validate(node))
        schema = transform_template_node_to_schema(node)
        self._schemas[lower_case(schema.get_namespace())] = schema

    def _add_schema_node(self, node: Node) -> None:
        self._throw_if_invalid(SchemaValidator(self._schema_meta, True).validate(node))
        schema = transform_node_to_schema(node)
        self._schemas[lower_case(schema.get_namespace())] = schema

    @staticmethod
    def _throw_if_invalid(errors: list[ValidationException]) -> None:
        # A schema/template that does not validate against its meta-schema must not be loaded
        if errors:
            raise errors[0]

    def clear(self) -> None:
        """Removes every schema and template registered in this provider."""
        self._schemas.clear()

    def get_all_schemas(self) -> list[Schema]:
        """Every schema registered in this provider, in registration order."""
        return list(self._schemas.values())


__all__ = ["UnifiedSchemaProvider"]
