"""ChildLine: the result of parsing the RuleSpec of a ``Structure >>`` line
(``stxt-impl/template/child_line.txt``)."""

from __future__ import annotations

from typing import Optional


class ChildLine:
    """Immutable container with the cardinality (min/max), the type and, for ENUM, the values.
    Any field may be ``None`` when it was not specified. ``values == []`` (empty but not
    ``None``) means the brackets were present but empty (``[]``)."""

    __slots__ = ("_type", "_min", "_max", "_values")

    def __init__(self, type: Optional[str], min: Optional[int], max: Optional[int],  # noqa: A002
                 values: Optional[list[str]]) -> None:
        self._type = type
        self._min = min
        self._max = max
        self._values = values

    def get_type(self) -> Optional[str]:
        """The type, an ``@Name`` reference, or ``None``."""
        return self._type

    def get_min(self) -> Optional[int]:
        return self._min

    def get_max(self) -> Optional[int]:
        return self._max

    def get_values(self) -> Optional[list[str]]:
        """ENUM values, or ``None`` when no brackets were present."""
        return self._values

    def __repr__(self) -> str:
        return f"ChildLine(type={self._type!r}, min={self._min}, max={self._max}, values={self._values})"
