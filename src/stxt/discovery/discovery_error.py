"""DiscoveryError: a resolution error (STXT-DISCOVERY-SPEC 8;
``stxt-impl/discovery/discovery_error.txt``). Resolution errors are COLLECTED, not raised."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DiscoveryError:
    """A resolution error, with the offending file and, when it applies, the namespace."""

    #: Two definitions for the same target namespace at the same level (8.1)
    DUPLICATE_NAMESPACE = "DISCOVERY_DUPLICATE_NAMESPACE"
    #: A file under a resolution directory that does not parse as STXT (8.2)
    NOT_PARSEABLE = "DISCOVERY_NOT_PARSEABLE"
    #: A file whose root node belongs neither to @stxt.schema nor to @stxt.template (8.3)
    NOT_A_DEFINITION = "DISCOVERY_NOT_A_DEFINITION"
    #: A definition that does not validate against its meta-schema (8.4)
    INVALID_DEFINITION = "DISCOVERY_INVALID_DEFINITION"

    code: str                       #: one of the DISCOVERY_* constants above
    file: str                       #: full path of the offending file
    message: str                    #: human-readable description
    namespace: Optional[str] = None  #: target namespace involved, or None


__all__ = ["DiscoveryError"]
