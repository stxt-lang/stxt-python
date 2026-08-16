"""DiscoveryFileSystem: minimal file-system abstraction used by :class:`DiscoveryResolver`
(``stxt-impl/discovery/discovery_file_system.txt``).

The resolver treats paths as OPAQUE STRINGS: it never parses or concatenates them itself, so
an implementation may back them with OS paths, editor URIs or an in-memory tree for tests.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DiscoveryEntry:
    """An entry of a directory listing."""

    path: str            #: full path, in the same form the file system uses everywhere
    name: str            #: base name (last path segment)
    is_directory: bool


class DiscoveryFileSystem(ABC):
    """The five file-system operations the resolver needs."""

    @abstractmethod
    def is_directory(self, path: str) -> bool:
        """True if the path exists and is a directory; False otherwise (I/O errors included)."""

    @abstractmethod
    def list_directory(self, path: str) -> list[DiscoveryEntry]:
        """The immediate entries of a directory, in any order."""

    @abstractmethod
    def read_file(self, path: str) -> str:
        """Reads a file as UTF-8 text."""

    @abstractmethod
    def parent_of(self, path: str) -> Optional[str]:
        """The parent directory of a path, or ``None`` when the path is the file-system root."""

    @abstractmethod
    def join(self, path: str, name: str) -> str:
        """Joins a directory path and a child name."""


class OsDiscoveryFileSystem(DiscoveryFileSystem):
    """The real file system, through :mod:`os` (paths are plain OS path strings)."""

    def is_directory(self, path: str) -> bool:
        try:
            return os.path.isdir(path)
        except OSError:
            return False

    def list_directory(self, path: str) -> list[DiscoveryEntry]:
        with os.scandir(path) as it:
            return [DiscoveryEntry(entry.path, entry.name, entry.is_dir()) for entry in it]

    def read_file(self, path: str) -> str:
        with open(path, encoding="utf-8") as f:
            return f.read()

    def parent_of(self, path: str) -> Optional[str]:
        parent = os.path.dirname(path)
        if parent == path or parent == "":
            return None
        return parent

    def join(self, path: str, name: str) -> str:
        return os.path.join(path, name)


__all__ = ["DiscoveryEntry", "DiscoveryFileSystem", "OsDiscoveryFileSystem"]
