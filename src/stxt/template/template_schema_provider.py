"""Template providers: obtain a Schema from ``@stxt.template`` documents
(``stxt-impl/template/template_schema_provider.txt``)."""

from __future__ import annotations

from typing import Optional

from ..core.parser import Parser
from ..exceptions import ParseException, ValidationException
from ..schema.definition_compiler import compile_document
from ..schema.schema import Schema
from ..schema.schema_provider import SchemaProvider, SchemaProviderMemory
from .template_parser import TEMPLATE_NAMESPACE, transform_template_node_to_schema

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

    #: Compiled once per process and shared between instances, exactly like the ``_meta``
    #: of :class:`~stxt.schema.schema_provider.SchemaProviderMeta`.
    _meta: Optional[Schema] = None

    def __init__(self) -> None:
        if MetaTemplateSchemaProvider._meta is None:
            MetaTemplateSchemaProvider._meta = self._compile()

    @staticmethod
    def _compile() -> Schema:
        nodes = Parser().parse(META_TEXT)
        if len(nodes) != 1:
            raise ValidationException(ParseException.NO_LINE, "META_SCHEMA_INVALID",
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
        registers the schema it produces. The whole pipeline is the shared one of
        :mod:`~stxt.schema.definition_compiler`; an empty target namespace is rejected by
        the template parser (``TEMPLATE_NAMESPACE_EMPTY``).

        Raises:
            ParseException: if the document does not parse.
            ValidationException: the first meta-template error, or ``TEMPLATE_MULTIPLE_ROOTS``.
        """
        schema = compile_document(template, MetaTemplateSchemaProvider(),
                                  transform_template_node_to_schema, "TEMPLATE_MULTIPLE_ROOTS", "template")

        self._schemas[schema.get_namespace()] = schema


__all__ = ["MetaTemplateSchemaProvider", "TemplateSchemaProviderMemory", "TEMPLATE_NAMESPACE", "META_TEXT"]
