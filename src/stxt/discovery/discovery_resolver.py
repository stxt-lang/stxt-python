"""DiscoveryResolver: reference implementation of STXT-DISCOVERY-SPEC
(``stxt-impl/discovery/discovery_resolver.txt``).

It builds the resolution chain of a document (project ascent, user level, system level, or
the ``STXT_PATH`` override), loads every definition of every level and applies the
per-namespace precedence. Loaded levels are cached by directory (call :meth:`clear_cache`
when the files may have changed).
"""

from __future__ import annotations

from typing import Optional

from ..core.node import Node
from ..core.parser import Parser
from ..core.string_utils import lower_case
from ..schema.definition_compiler import compile_node
from ..schema.schema import SCHEMA_NAMESPACE, TEMPLATE_NAMESPACE
from ..schema.schema_parser import transform_node_to_schema
from ..schema.schema_provider import SchemaProvider, SchemaProviderMeta
from ..template.template_parser import transform_template_node_to_schema
from ..template.template_schema_provider import MetaTemplateSchemaProvider
from .discovery_environment import DiscoveryEnvironment, SystemDiscoveryEnvironment
from .discovery_error import DiscoveryError
from .discovery_file_system import DiscoveryEntry, DiscoveryFileSystem, OsDiscoveryFileSystem
from .discovery_result import DiscoveryDefinition, DiscoveryLevel, DiscoveryResult

#: Name of the resolution directories (3)
STXT_DIR = ".stxt"
#: File extension of STXT documents
STXT_EXTENSION = ".stxt"
#: Default maximum number of ancestor directories examined during the project-level ascent
DEFAULT_MAX_ASCENT = 32
#: Default maximum depth of the recursive descent inside a resolution directory. A safeguard
#: against symlink loops and pathological trees, analogous to the ascent limit (DISCOVERY-SPEC
#: §3, §10); the descent stops at this depth instead of recursing without bound. Internal: it is
#: not exposed in the constructor nor in the public API.
DEFAULT_MAX_DESCENT = 32


class DiscoveryResolver:
    """Host-agnostic resolver: file system and environment are injected."""

    def __init__(self, fs: DiscoveryFileSystem, env: DiscoveryEnvironment,
                 max_ascent: int = DEFAULT_MAX_ASCENT) -> None:
        self._fs = fs
        self._env = env
        self._max_ascent = max_ascent
        self._schema_meta: SchemaProvider = SchemaProviderMeta()
        self._template_meta: SchemaProvider = MetaTemplateSchemaProvider()
        self._level_cache: dict[str, DiscoveryLevel] = {}

    # ---------------------------------------------------------------- chain (4 and 6)

    def resolve_chain(self, document_dir: Optional[str]) -> list[str]:
        """Builds the resolution chain of a document without loading any definition.

        ``document_dir`` is the directory containing the document, or ``None`` for a document
        with no file-system location (standard input, an unsaved buffer), whose chain starts
        at the user level. Returns the EXISTING resolution directories, highest precedence
        first.
        """
        # STXT_PATH, when defined, completely replaces the chain (6)
        stxt_path = self._env.get_stxt_path()
        if stxt_path is not None:
            return self._existing_unique(stxt_path)

        chain: list[str] = []

        # Project level: every .stxt directory from the document's directory upward (4.1)
        if document_dir is not None:
            directory: Optional[str] = document_dir
            ascended = 0
            while ascended < self._max_ascent and directory is not None:
                candidate = self._fs.join(directory, STXT_DIR)
                if self._fs.is_directory(candidate):
                    chain.append(candidate)
                directory = self._fs.parent_of(directory)
                ascended += 1

        # User and system levels (4.2). The ascent may have reached them already: deduplicate.
        for directory in (self._env.get_user_level_dir(), self._env.get_system_level_dir()):
            if directory is not None and directory not in chain and self._fs.is_directory(directory):
                chain.append(directory)

        return chain

    def resolve(self, document_dir: Optional[str]) -> DiscoveryResult:
        """Resolves the definitions applicable to a document: builds its chain, loads every level
        (from the cache when already loaded) and returns the result with the per-namespace
        precedence applied, usable directly as a :class:`SchemaProvider`."""
        levels = [self._load_level(directory) for directory in self.resolve_chain(document_dir)]
        return DiscoveryResult(levels, self._schema_meta, self._template_meta)

    def clear_cache(self) -> None:
        """Empties the level cache, so that the next resolve re-reads every directory."""
        self._level_cache = {}

    def _existing_unique(self, dirs: list[str]) -> list[str]:
        result: list[str] = []
        for directory in dirs:
            if directory not in result and self._fs.is_directory(directory):
                result.append(directory)
        return result

    # ---------------------------------------------------------------- levels (5, 7 and 8)

    def _load_level(self, directory: str) -> DiscoveryLevel:
        cached = self._level_cache.get(directory)
        if cached is not None:
            return cached

        level = DiscoveryLevel(directory)
        for file in self._collect_files(directory):
            self._load_file(file, level)

        self._level_cache[directory] = level
        return level

    def _collect_files(self, directory: str) -> list[str]:
        # Every file under a directory, recursively, SORTED BY PATH so that results and error
        # messages do not depend on the listing order of the file system. The descent is bounded
        # by DEFAULT_MAX_DESCENT and tolerant of listing failures (DISCOVERY-SPEC §3, §10): a
        # subdirectory that reaches the depth limit or cannot be listed simply contributes no
        # files, never an exception. Together with adapters that do not follow directory symlinks,
        # this stops symlink loops and pathological trees from turning resolution into unbounded
        # recursion or an escaping exception.
        return self._collect_files_at(directory, 0)

    def _collect_files_at(self, directory: str, depth: int) -> list[str]:
        files: list[str] = []

        # Safeguard against symlink loops and pathological trees (§10): stop descending.
        if depth >= DEFAULT_MAX_DESCENT:
            return files

        try:
            entries = _sort_by_path(self._fs.list_directory(directory))
        except Exception:  # noqa: BLE001 - a directory that cannot be listed contributes no files (§3)
            return files

        for entry in entries:
            if entry.is_directory:
                files.extend(self._collect_files_at(entry.path, depth + 1))
            else:
                files.append(entry.path)
        return files

    def _load_file(self, file: str, level: DiscoveryLevel) -> None:
        # 3: every file under a resolution directory must be a definition
        if not file.endswith(STXT_EXTENSION):
            level.errors.append(DiscoveryError(DiscoveryError.NOT_A_DEFINITION, file,
                                               "Not an STXT definition file: " + file))
            return

        try:
            nodes = Parser().parse(self._fs.read_file(file))
        except Exception as e:  # noqa: BLE001 - reported as a resolution error
            level.errors.append(DiscoveryError(DiscoveryError.NOT_PARSEABLE, file,
                                               f"Cannot parse {file}: {_message(e)}"))
            return

        if len(nodes) == 0:
            level.errors.append(DiscoveryError(DiscoveryError.NOT_A_DEFINITION, file,
                                               "Empty document, not a definition: " + file))
            return

        for node in nodes:
            self._load_root_node(node, file, level)

    def _load_root_node(self, node: Node, file: str, level: DiscoveryLevel) -> None:
        namespace = node.get_namespace()

        try:
            if namespace == TEMPLATE_NAMESPACE:
                schema = compile_node(node, self._template_meta, transform_template_node_to_schema)
            elif namespace == SCHEMA_NAMESPACE:
                schema = compile_node(node, self._schema_meta, transform_node_to_schema)
            else:
                level.errors.append(DiscoveryError(DiscoveryError.NOT_A_DEFINITION, file,
                                                   f"Root node belongs to '{namespace}', not to @stxt.schema or @stxt.template: {file}"))
                return
        except Exception as e:  # noqa: BLE001 - reported as a resolution error
            level.errors.append(DiscoveryError(DiscoveryError.INVALID_DEFINITION, file,
                                               f"Invalid definition in {file}: {_message(e)}"))
            return

        key = lower_case(schema.get_namespace())

        # 8.1: on a same-level duplicate, NEVER silently pick one of the definitions — the
        # namespace has no active definition while the conflict exists, including definitions
        # at more distant levels.
        if key in level.conflicted_namespaces or key in level.definitions:
            first_file = "another file of this level"
            if key in level.definitions:
                first_file = level.definitions[key].file
                del level.definitions[key]
                level.conflicted_namespaces.append(key)

            level.errors.append(DiscoveryError(
                DiscoveryError.DUPLICATE_NAMESPACE, file,
                f"Duplicate definition for namespace '{schema.get_namespace()}' at level {level.dir}: "
                f"already defined in {first_file}",
                schema.get_namespace()))
            return

        level.definitions[key] = DiscoveryDefinition(schema.get_namespace(), schema, file, level.dir)

    # Compilation itself is the shared pipeline of stxt.schema.definition_compiler
    # (compile_node): validate against the meta of the kind, raise the first error, transform.


def _sort_by_path(entries: list[DiscoveryEntry]) -> list[DiscoveryEntry]:
    return sorted(entries, key=lambda entry: entry.path)


def _message(e: Exception) -> str:
    return getattr(e, "message", None) or str(e)


def resolve(document_dir: Optional[str], max_ascent: int = DEFAULT_MAX_ASCENT) -> DiscoveryResult:
    """Resolves the definitions applicable to a document on the real host (OS file system and
    process environment). A convenience over :class:`DiscoveryResolver`."""
    return DiscoveryResolver(OsDiscoveryFileSystem(), SystemDiscoveryEnvironment(), max_ascent).resolve(document_dir)


__all__ = ["DiscoveryResolver", "resolve", "STXT_DIR", "STXT_EXTENSION", "DEFAULT_MAX_ASCENT"]
