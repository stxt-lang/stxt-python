"""STXT for Python: parser, node model, schemas, templates, canonical tree,
writer and discovery.

The language is defined by the specifications at https://stxt.dev; this package is a port of
the neutral blueprint ``stxt-impl`` and shares its behaviour and error codes with the
TypeScript (``@stxt-lang/core``) and Java (``dev.stxt:stxt-core``) ports.

Quick start::

    from stxt import Parser, InlineNode

    for root in Parser().parse("Doc (com.example.docs): Hello\\n\\tBody >>\\n\\t\\tline\\n"):
        print(root.get_name(), root.get_namespace())
        if isinstance(root, InlineNode):
            for child in root.get_children():
                print("  ", child.get_name(), child.get_text())
"""

from .core.constants import EMPTY_NAMESPACE, SPEC_VERSION
from .core.line_indent import LineIndent, parse_line
from .core.node import NO_LINE, InlineNode, Node, TextNode
from .core.parse_result import ParseResult
from .core.parser import Parser
from .discovery import (
    DiscoveryDefinition,
    DiscoveryEntry,
    DiscoveryEnvironment,
    DiscoveryError,
    DiscoveryFileSystem,
    DiscoveryLevel,
    DiscoveryResolver,
    DiscoveryResult,
    OsDiscoveryFileSystem,
    SystemDiscoveryEnvironment,
)
from .exceptions import LimitException, ParseException, RuntimeException, ValidationException
from .processors import Observer, StreamObserver, Validator
from .runtime import (
    Formatter,
    FormatResult,
    IndentStyle,
    NodeWriter,
    UnifiedSchemaProvider,
    to_canonical_json,
    to_canonical_tree,
)
from .schema import (
    SCHEMA_NAMESPACE,
    ChildDefinition,
    NodeDefinition,
    Schema,
    SchemaProvider,
    SchemaProviderMemory,
    SchemaProviderMeta,
    SchemaValidator,
    Type,
    TypeRegistry,
    transform_node_to_schema,
)
from .template import (
    MetaTemplateSchemaProvider,
    TemplateSchemaProviderMemory,
    transform_template_node_to_schema,
)
from .template.template_schema_provider import TEMPLATE_NAMESPACE

__version__ = "0.15.0"

__all__ = [
    "__version__", "SPEC_VERSION",
    # core
    "Parser", "ParseResult", "Node", "InlineNode", "TextNode", "NO_LINE", "LineIndent", "parse_line",
    "EMPTY_NAMESPACE",
    # exceptions
    "ParseException", "ValidationException", "LimitException", "RuntimeException",
    # processors
    "Observer", "StreamObserver", "Validator",
    # schema
    "Schema", "SCHEMA_NAMESPACE", "NodeDefinition", "ChildDefinition", "SchemaProvider",
    "SchemaProviderMemory", "SchemaProviderMeta", "SchemaValidator", "transform_node_to_schema",
    "Type", "TypeRegistry",
    # template
    "TEMPLATE_NAMESPACE", "MetaTemplateSchemaProvider", "TemplateSchemaProviderMemory",
    "transform_template_node_to_schema",
    # runtime
    "NodeWriter", "IndentStyle", "Formatter", "FormatResult", "to_canonical_tree", "to_canonical_json",
    "UnifiedSchemaProvider",
    # discovery
    "DiscoveryResolver", "DiscoveryResult", "DiscoveryDefinition", "DiscoveryLevel", "DiscoveryError",
    "DiscoveryFileSystem", "DiscoveryEntry", "DiscoveryEnvironment", "OsDiscoveryFileSystem",
    "SystemDiscoveryEnvironment",
]
