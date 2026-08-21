"""Template providers: obtain a Schema from ``@stxt.template`` documents
(``stxt-impl/template/template_schema_provider.txt``)."""

from __future__ import annotations

from typing import Optional

from ..core.parser import Parser
from ..core.string_utils import is_empty
from ..exceptions import ValidationException
from ..schema.schema import Schema
from ..schema.schema_provider import SchemaProvider, SchemaProviderMemory
from ..schema.schema_validator import SchemaValidator
from .template_parser import TEMPLATE_NAMESPACE, transform_template_node_to_schema

#: Namespace of the template language itself.

# The meta-template of the template language itself, embedded verbatim: STXT-TEMPLATE-SPEC 16.
META_TEXT = """Template (@stxt.template): @stxt.template
	Structure >>
		Template (@stxt.template):
			Description: (?) TEXT
			Structure: (1) BLOCK
"""


class MetaTemplateSchemaProvider(SchemaProvider):
    """Provider of the embedded meta-template (``@stxt.template``), so that a loaded template
    can validate itself (bootstrap). ``None`` for any other namespace."""

    META_TEXT = META_TEXT
    _meta: Optional[Schema] = None

    def __init__(self) -> None:
        if MetaTemplateSchemaProvider._meta is None:
            MetaTemplateSchemaProvider._meta = self._compile()

    @staticmethod
    def _compile() -> Schema:
        nodes = Parser().parse(META_TEXT)
        if len(nodes) != 1:
            raise ValidationException(0, "META_SCHEMA_INVALID",
                                      f"Meta schema must produce exactly 1 document, got {len(nodes)}")
        # The meta-template itself is compiled with the template parser
        return transform_template_node_to_schema(nodes[0])

    def get_schema(self, namespace: str) -> Optional[Schema]:
        if namespace != TEMPLATE_NAMESPACE:
            return None
        return MetaTemplateSchemaProvider._meta


class TemplateSchemaProviderMemory(SchemaProviderMemory):
    """In-memory provider fed with template documents. Each template is turned into its
    equivalent Schema and registered under its own namespace. Inherits ``get_schema()`` /
    ``clear()`` / ``get_all_schemas()`` from :class:`SchemaProviderMemory`."""

    def __init__(self, parent: Optional[SchemaProvider] = None) -> None:
        super().__init__(parent if parent is not None else MetaTemplateSchemaProvider())

    def add_template(self, template: str) -> None:
        """Parses a template document, validates it against the template meta-schema and
        registers the schema it produces.

        Raises:
            ParseException: if the document does not parse.
            ValidationException: the first meta-template error, or ``TEMPLATE_MULTIPLE_ROOTS``.
        """
        nodes = Parser().parse(template)
        if len(nodes) != 1:
            raise ValidationException(0, "TEMPLATE_MULTIPLE_ROOTS", f"There are {len(nodes)} root nodes, and expected is 1")
        node = nodes[0]

        # The document must validate against the meta-template (@stxt.template)
        errors = SchemaValidator(MetaTemplateSchemaProvider(), True).validate(node)
        if errors:
            raise errors[0]

        schema = transform_template_node_to_schema(node)
        if is_empty(schema.get_namespace()):
            raise ValidationException(node.get_line(), "TEMPLATE_NAMESPACE_EMPTY", "Template namespace is empty")

        self._schemas[schema.get_namespace()] = schema


__all__ = ["MetaTemplateSchemaProvider", "TemplateSchemaProviderMemory", "TEMPLATE_NAMESPACE", "META_TEXT"]
