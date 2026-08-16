"""STXT-DISCOVERY-SPEC: how tools locate the schemas and templates that apply to a document.

The resolver is host-agnostic: all file-system and environment access goes through the
injected :class:`DiscoveryFileSystem` and :class:`DiscoveryEnvironment`. This package also
ships the two host adapters of the port, :class:`OsDiscoveryFileSystem` and
:class:`SystemDiscoveryEnvironment`, plus :func:`resolve` for the common case.
"""

from .discovery_environment import DiscoveryEnvironment, SystemDiscoveryEnvironment
from .discovery_error import DiscoveryError
from .discovery_file_system import DiscoveryEntry, DiscoveryFileSystem, OsDiscoveryFileSystem
from .discovery_resolver import DEFAULT_MAX_ASCENT, STXT_DIR, STXT_EXTENSION, DiscoveryResolver, resolve
from .discovery_result import DiscoveryDefinition, DiscoveryLevel, DiscoveryResult

__all__ = [
    "DiscoveryEnvironment", "SystemDiscoveryEnvironment", "DiscoveryError", "DiscoveryEntry",
    "DiscoveryFileSystem", "OsDiscoveryFileSystem", "DiscoveryResolver", "resolve",
    "DiscoveryDefinition", "DiscoveryLevel", "DiscoveryResult",
    "DEFAULT_MAX_ASCENT", "STXT_DIR", "STXT_EXTENSION",
]
