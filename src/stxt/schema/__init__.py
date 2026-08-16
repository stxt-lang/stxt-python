"""STXT-SCHEMA-SPEC: the ``@stxt.schema`` model, parser, providers, validator and value types."""

from .child_definition import ChildDefinition
from .node_definition import NodeDefinition
from .schema import SCHEMA_NAMESPACE, Schema
from .schema_parser import transform_node_to_schema
from .schema_provider import SchemaProvider, SchemaProviderMemory, SchemaProviderMeta
from .schema_validator import SchemaValidator
from .types import Type, TypeRegistry

__all__ = [
    "ChildDefinition", "NodeDefinition", "Schema", "SCHEMA_NAMESPACE",
    "transform_node_to_schema", "SchemaProvider", "SchemaProviderMemory", "SchemaProviderMeta",
    "SchemaValidator", "Type", "TypeRegistry",
]
