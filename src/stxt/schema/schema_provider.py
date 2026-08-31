"""SchemaProvider: resolves the Schema that applies to a namespace
(``stxt-impl/schema/schema_provider.txt``).

CONTRACT: ``get_schema()`` returns the Schema, or ``None`` when the provider has no schema for
that namespace. Providers do NOT raise "not found" errors: it is the consumer (typically
:class:`SchemaValidator`) who reports ``SCHEMA_NOT_FOUND`` when the resolution ends in
``None``. The rule has no exceptions (meta providers, external stores, caches, chains).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..core.string_utils import lower_case
from ..exceptions import ParseException, ValidationException
from .schema import SCHEMA_NAMESPACE, Schema


class SchemaProvider(ABC):
    """Resolves the schema of a namespace; ``None`` when it has none for it."""

    @abstractmethod
    def get_schema(self, namespace: str) -> Optional[Schema]:
        """The schema of the namespace, or ``None`` if this provider has none for it."""


class SchemaProviderMemory(SchemaProvider):
    """In-memory provider with parent fallback.

    Keeps the schemas added with :meth:`add_schema` indexed by namespace, and falls back to a
    parent provider (the meta-schema provider by default) for the namespaces it does not know.
    """

    def __init__(self, parent: Optional[SchemaProvider] = None) -> None:
        self._parent: SchemaProvider = parent if parent is not None else SchemaProviderMeta()
        # key = lowercased namespace, insertion order
        self._schemas: dict[str, Schema] = {}

    def get_schema(self, namespace: str) -> Optional[Schema]:
        result = self._schemas.get(lower_case(namespace))
        if result is None:
            result = self._parent.get_schema(namespace)
        return result

    def add_schema(self, text: str) -> None:
        """Parses a schema document, validates it against the meta-schema and registers it
        under its own namespace. The whole pipeline is the shared one of
        :mod:`~stxt.schema.definition_compiler`; an empty target namespace is rejected by
        the schema parser (``SCHEMA_NAMESPACE_EMPTY``).

        Raises:
            ParseException: if the document does not parse.
            ValidationException: the first meta-schema error, or ``SCHEMA_MULTIPLE_ROOTS``.
        """
        from .definition_compiler import compile_document
        from .schema_parser import transform_node_to_schema

        schema = compile_document(text, SchemaProviderMeta(), transform_node_to_schema,
                                  "SCHEMA_MULTIPLE_ROOTS", "schema")

        self._schemas[schema.get_namespace()] = schema

    def clear(self) -> None:
        """Removes every schema registered here (the parent is left untouched)."""
        self._schemas = {}

    def get_all_schemas(self) -> list[Schema]:
        """Every schema registered here, in registration order."""
        return list(self._schemas.values())


# The meta-schema of the schema language itself, embedded verbatim: STXT-SCHEMA-SPEC 15.2.
META_TEXT = """Schema (@stxt.schema): @stxt.schema
	Node: Schema
		Children:
			Child: Description
				Max: 1
			Child: Node
				Min: 1
	Node: Node
		Children:
			Child: Type
				Max: 1
			Child: Children
				Max: 1
			Child: Description
				Max: 1
			Child: Values
				Max: 1
	Node: Children
		Type: GROUP
		Children:
			Child: Child
				Min: 1
	Node: Description
		Type: TEXT
	Node: Child
		Children:
			Child: Min
				Max: 1
			Child: Max
				Max: 1
	Node: Min
		Type: NATURAL
	Node: Max
		Type: NATURAL
	Node: Type
		Type: ENUM
		Values:
			Value: INLINE
			Value: BLOCK
			Value: TEXT
			Value: BOOLEAN
			Value: URL
			Value: INTEGER
			Value: NATURAL
			Value: NUMBER
			Value: DATE
			Value: TIME
			Value: TIMESTAMP
			Value: UUID
			Value: EMAIL
			Value: HEXADECIMAL
			Value: BINARY
			Value: BASE64
			Value: GROUP
			Value: ENUM
			Value: MARKDOWN
	Node: Values
		Type: GROUP
		Children:
			Child: Value
				Min: 1
	Node: Value
"""


class SchemaProviderMeta(SchemaProvider):
    """Provider of the embedded meta-schema (``@stxt.schema``), so that a loaded schema can
    validate itself (bootstrap). ``None`` for any other namespace."""

    META_TEXT = META_TEXT

    #: The meta-schema is immutable, so it is compiled once per process, lazily, and every
    #: instance serves this same schema (constructing these providers is common: every
    #: ``add_schema()`` and every discovery compilation builds one).
    _meta: Optional[Schema] = None

    def __init__(self) -> None:
        if SchemaProviderMeta._meta is None:
            SchemaProviderMeta._meta = self._compile()

    @staticmethod
    def _compile() -> Schema:
        from ..core.parser import Parser
        from .schema_parser import transform_node_to_schema

        nodes = Parser().parse(META_TEXT)
        if len(nodes) != 1:
            raise ValidationException(ParseException.NO_LINE, "META_SCHEMA_INVALID",
                                      f"Meta schema must produce exactly 1 document, got {len(nodes)}")
        return transform_node_to_schema(nodes[0])

    def get_schema(self, namespace: str) -> Optional[Schema]:
        if namespace != SCHEMA_NAMESPACE:
            return None
        return SchemaProviderMeta._meta


__all__ = ["SchemaProvider", "SchemaProviderMemory", "SchemaProviderMeta", "META_TEXT"]
