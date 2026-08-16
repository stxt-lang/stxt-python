"""DiscoveryEnvironment: environment abstraction used by :class:`DiscoveryResolver`
(``stxt-impl/discovery/discovery_environment.txt``)."""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class DiscoveryEnvironment(ABC):
    """Answers the three questions that depend on the platform and the process environment."""

    @abstractmethod
    def get_stxt_path(self) -> Optional[list[str]]:
        """The value of ``STXT_PATH``, already split into entries (highest precedence first).

        The distinction between "not defined" and "defined but empty" is normative
        (STXT-DISCOVERY-SPEC 6): return an empty list when defined but empty, and ``None``
        when it is not defined at all.
        """

    @abstractmethod
    def get_user_level_dir(self) -> Optional[str]:
        """The user-level resolution directory (``$HOME/.stxt`` on Unix,
        ``%USERPROFILE%\\.stxt`` on Windows), or ``None`` when the host has no user home."""

    @abstractmethod
    def get_system_level_dir(self) -> Optional[str]:
        """The system-level resolution directory (``/etc/stxt`` on Unix,
        ``%ProgramData%\\stxt`` on Windows), or ``None`` when the host has no system level."""


class SystemDiscoveryEnvironment(DiscoveryEnvironment):
    """The real process environment: ``os.environ`` and the user's home."""

    def get_stxt_path(self) -> Optional[list[str]]:
        value = os.environ.get("STXT_PATH")
        if value is None:
            return None
        if value == "":
            return []
        return value.split(os.pathsep)

    def get_user_level_dir(self) -> Optional[str]:
        try:
            home = Path.home()
        except (RuntimeError, KeyError):
            return None
        return str(home / ".stxt")

    def get_system_level_dir(self) -> Optional[str]:
        if sys.platform.startswith("win"):
            program_data = os.environ.get("ProgramData")
            return None if program_data is None else str(Path(program_data) / "stxt")
        return "/etc/stxt"


__all__ = ["DiscoveryEnvironment", "SystemDiscoveryEnvironment"]
