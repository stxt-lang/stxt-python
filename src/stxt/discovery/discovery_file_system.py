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

from ..core.constants import DEFAULT_MAX_INPUT_SIZE

#: Largest definition file a resolution directory loads: the parser's default input limit
#: in characters, times the 4 bytes a character takes at most in UTF-8.
MAX_DEFINITION_FILE_BYTES = 4 * DEFAULT_MAX_INPUT_SIZE


@dataclass(frozen=True)
class DiscoveryEntry:
    """An entry of a directory listing."""

    path: str            #: full path, in the same form the file system uses everywhere
    name: str            #: base name (last path segment)
    is_directory: bool


class DiscoveryFileSystem(ABC):
    """The file-system operations the resolver needs: five abstract ones, and one with a default."""

    @abstractmethod
    def is_directory(self, path: str) -> bool:
        """True if the path exists and is a directory; False otherwise (I/O errors included).
        Follows symbolic links: a linked user level, system level or ``STXT_PATH`` entry is a
        directory (DISCOVERY-SPEC 4.2, 6)."""

    def is_symbolic_link(self, path: str) -> bool:
        """True if the path is a symbolic link — or, on Windows, a junction where Python tells
        them apart — whatever it points to and whether or not the target exists; False otherwise
        (I/O errors included). Only consulted during the project-level ascent (DISCOVERY-SPEC
        4.1): the ``.stxt`` of an ancestor that is itself a link forms no level. The default
        answers False, for an implementation over an abstraction with no links (an in-memory
        tree, a ZIP) and for every implementation written before the operation existed."""
        return False

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

    def is_symbolic_link(self, path: str) -> bool:
        # The link itself, whatever it points to (DISCOVERY-SPEC 4.1: a linked ancestor .stxt
        # forms no level). islink() is False for a Windows junction; os.path.isjunction (3.12+)
        # tells those apart where it exists.
        try:
            if os.path.islink(path):
                return True
            is_junction = getattr(os.path, "isjunction", None)
            return is_junction is not None and bool(is_junction(path))
        except OSError:
            return False

    def list_directory(self, path: str) -> list[DiscoveryEntry]:
        # Symbolic links are NOT followed at all (DISCOVERY-SPEC §3, §10): every symlink entry
        # is omitted from the listing, so a resolution directory loads only the real files it
        # contains. A directory link could lure the recursive descent into a loop or an unrelated
        # tree; a file link could read a file from outside the .stxt/ (and leak its content
        # through a resolution error). OSError from scandir/is_symlink/is_dir is tolerated here —
        # never propagated — even though the resolver also tolerates it per-directory.
        entries: list[DiscoveryEntry] = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue  # never follow a symlink (directory or file)
                        is_dir = entry.is_dir(follow_symlinks=False)
                        if not is_dir and not entry.is_file(follow_symlinks=False):
                            continue  # a FIFO, socket or device: open() could block forever
                        entries.append(DiscoveryEntry(entry.path, entry.name, is_dir))
                    except OSError:
                        continue  # an entry that cannot be stat'd contributes nothing
        except OSError:
            return []
        return entries

    def read_file(self, path: str) -> str:
        # A definition is parsed with the default limits (DEFAULT_MAX_INPUT_SIZE characters, at
        # most 4 bytes each in UTF-8), so a bigger file cannot be within them: rejected by size
        # before it is read whole, which kept the memory of a load proportional to the file
        # instead of to the limit. The OSError becomes a DISCOVERY_NOT_PARSEABLE error.
        if os.path.getsize(path) > MAX_DEFINITION_FILE_BYTES:
            raise OSError(f"Definition file larger than {MAX_DEFINITION_FILE_BYTES} bytes: {path}")
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
