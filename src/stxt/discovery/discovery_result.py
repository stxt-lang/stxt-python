"""DiscoveryResult: the outcome of resolving a document's definitions
(``stxt-impl/discovery/discovery_result.txt``). It implements :class:`SchemaProvider`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..core.string_utils import lower_case
from ..schema.schema import SCHEMA_NAMESPACE, Schema
from ..schema.schema_provider import SchemaProvider
from ..template.template_schema_provider import TEMPLATE_NAMESPACE
from .discovery_error import DiscoveryError


@dataclass(frozen=True)
class DiscoveryDefinition:
    """An active definition: a schema or template that won the per-namespace precedence,
    together with where it came from (provenance)."""

    namespace: str      #: target namespace, as written in the definition document
    schema: Schema      #: the compiled schema (templates compile to schemas at load time)
    file: str           #: full path of the file the definition was read from
    level_dir: str      #: resolution directory (level) the file belongs to


@dataclass
class DiscoveryLevel:
    """A loaded resolution directory: its definitions indexed by lowercased target namespace.
    Namespaces in conflict inside the level (8.1) are excluded from the map."""

    dir: str
    definitions: dict[str, DiscoveryDefinition] = field(default_factory=dict)
    #: Target namespaces with two or more definitions in this level; a conflict blocks
    #: fallback to lower levels.
    conflicted_namespaces: list[str] = field(default_factory=list)
    errors: list[DiscoveryError] = field(default_factory=list)


class DiscoveryResult(SchemaProvider):
    """The chain of levels, the active definition per namespace (nearest level wins) and every
    resolution error found. Serves the meta-schemas of the two reserved namespaces itself."""

    def __init__(self, levels: list[DiscoveryLevel], schema_meta: SchemaProvider,
                 template_meta: SchemaProvider) -> None:
        self._levels = levels
        self._schema_meta = schema_meta
        self._template_meta = template_meta

    def get_schema(self, namespace: str) -> Optional[Schema]:
        """The meta-schemas for the two reserved namespaces, otherwise the active definition of
        the nearest level; ``None`` if the chain has none (SchemaProvider contract)."""
        if namespace == TEMPLATE_NAMESPACE:
            return self._template_meta.get_schema(namespace)
        if namespace == SCHEMA_NAMESPACE:
            return self._schema_meta.get_schema(namespace)
        definition = self.get_definition(namespace)
        return None if definition is None else definition.schema

    def get_definition(self, namespace: str) -> Optional[DiscoveryDefinition]:
        """The active definition of a namespace: the one from the NEAREST level that defines it
        (5), with its provenance. A same-level conflict leaves the namespace without an active
        definition: no fallback to a more distant level (8)."""
        key = lower_case(namespace)
        for level in self._levels:
            if key in level.conflicted_namespaces:
                return None
            if key in level.definitions:
                return level.definitions[key]
        return None

    def get_active_definitions(self) -> list[DiscoveryDefinition]:
        """Every active definition of the chain, one per namespace, from its nearest level."""
        seen: set[str] = set()
        result: list[DiscoveryDefinition] = []
        for level in self._levels:
            # A nearer conflict blocks the namespace entirely, just like get_definition()
            seen.update(level.conflicted_namespaces)
            for key, definition in level.definitions.items():
                if key not in seen:
                    seen.add(key)
                    result.append(definition)
        return result

    def get_all_schemas(self) -> list[Schema]:
        """Every active schema of the chain."""
        return [definition.schema for definition in self.get_active_definitions()]

    def get_chain(self) -> list[str]:
        """The loaded level directories, highest precedence first."""
        return [level.dir for level in self._levels]

    def get_errors(self) -> list[DiscoveryError]:
        """Every resolution error found while loading the chain, by level and then by file."""
        result: list[DiscoveryError] = []
        for level in self._levels:
            result.extend(level.errors)
        return result


__all__ = ["DiscoveryDefinition", "DiscoveryLevel", "DiscoveryResult"]
