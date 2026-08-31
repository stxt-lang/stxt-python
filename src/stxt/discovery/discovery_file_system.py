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
        # Directory symbolic links are NOT followed (DISCOVERY-SPEC §3, §10): a symlink that
        # points to a directory is omitted from the listing, so the resolver's recursive descent
        # cannot be lured into a symlink loop or into an unrelated tree. A symlink to a regular
        # file is still listed as a file. OSError from scandir/is_dir (an ELOOP or a directory
        # that cannot be read) is tolerated here — never propagated — even though the resolver
        # also tolerates it per-directory.
        entries: list[DiscoveryEntry] = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # A real directory: recurse into it.
                            entries.append(DiscoveryEntry(entry.path, entry.name, True))
                        elif entry.is_dir(follow_symlinks=True):
                            # A symlink pointing to a directory: omit it entirely, so the descent
                            # is never lured into a loop or an unrelated tree.
                            continue
                        else:
                            # A regular file, or a symlink to a regular file: listed as a file.
                            entries.append(DiscoveryEntry(entry.path, entry.name, False))
                    except OSError:
                        # A broken or looping symlink: treat as a plain, non-recursed entry.
                        entries.append(DiscoveryEntry(entry.path, entry.name, False))
        except OSError:
            return []
        return entries

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
