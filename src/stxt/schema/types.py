"""Schema value types (``stxt-impl/schema/types.txt``; STXT-SCHEMA-SPEC section 9).

Each type knows how to validate the value shape of a node and, optionally, its content.
Two-property model: value form (INLINE, BLOCK, INLINE/BLOCK or NONE) and whether children
are accepted (only INLINE and GROUP accept children; the rest are leaves).

Following the blueprint, every type lives in this one module; they are registered once in
:class:`TypeRegistry` at import time.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Callable, Optional

from ..core.node import InlineNode, Node, TextNode
from ..core.platform import is_valid_base64
from ..core.string_utils import is_empty
from ..exceptions import RuntimeException, ValidationException
from .node_definition import NodeDefinition


class Type(ABC):
    """A schema value type, identified by its name as written in ``Type:``."""

    @abstractmethod
    def get_name(self) -> str:
        """Name of the type, as written in ``Type:``."""

    @abstractmethod
    def validate(self, ns_node: NodeDefinition, node: Node) -> None:
        """Validates ``node`` against its definition.

        Raises:
            ValidationException: on failure.
        """


def _not_allowed_text(n: Node) -> ValidationException:
    return ValidationException(n.get_line(), "BLOCK_FORM_NOT_ALLOWED",
                               f"Not allowed text in node {n.get_qualified_name()}")


def binary_value(node: Node) -> str:
    """Effective value for the INLINE/BLOCK binary types (HEXADECIMAL, BINARY, BASE64).

    Every blank (U+0020 space, U+0009 tab) is removed wherever it is, in both forms; in BLOCK
    form the lines are concatenated, which also drops line breaks and empty lines. So
    ``DE AD BE EF``, ``1010 1010`` and Base64 wrapped at 76 columns validate. No other
    character is removed: ``DE:AD`` or ``DE-AD`` stay invalid (STXT-SCHEMA-SPEC 9.5, since
    2026-08-21).
    """
    raw = "".join(node.get_text_lines()) if isinstance(node, TextNode) else node.get_text()
    return raw.replace(" ", "").replace("\t", "")


# ---------------------------------------------------------------- structural types

class INLINE(Type):
    """Optional inline value, no text block. Accepts children. Default type."""

    def get_name(self) -> str:
        return "INLINE"

    def validate(self, ns_node: NodeDefinition, node: Node) -> None:
        if node.is_text_node():
            raise _not_allowed_text(node)


class GROUP(Type):
    """Structure only (children). Neither an inline value nor a ``>>`` block."""

    def get_name(self) -> str:
        return "GROUP"

    def validate(self, ns_node: NodeDefinition, node: Node) -> None:
        if node.is_text_node() or not is_empty(node.get_text()):
            raise ValidationException(node.get_line(), "VALUE_NOT_ALLOWED",
                                      f"Node '{node.get_name()}' has to be empty")


class BLOCK(Type):
    """Text block ``>>`` only. The inline form is not allowed."""

    def get_name(self) -> str:
        return "BLOCK"

    def validate(self, ns_node: NodeDefinition, node: Node) -> None:
        if not node.is_text_node():
            raise ValidationException(node.get_line(), "BLOCK_FORM_REQUIRED",
                                      f"Node {node.get_qualified_name()} requires block form '>>'")


class TEXT(Type):
    """Free text, inline or block. No children allowed."""

    def get_name(self) -> str:
        return "TEXT"

    def validate(self, ns_node: NodeDefinition, node: Node) -> None:
        if isinstance(node, InlineNode) and len(node.get_children()) > 0:
            raise ValidationException(node.get_line(), "CHILDREN_NOT_ALLOWED",
                                      f"Not allowed children nodes in node {node.get_qualified_name()}")


class MARKDOWN(TEXT):
    """Markdown content (9.7). For validation it is equivalent to TEXT (any content is valid
    Markdown; only children are forbidden), so it inherits the validation and only the name
    differs."""

    def get_name(self) -> str:
        return "MARKDOWN"


class ENUM(Type):
    """The inline value must match exactly (case-sensitive) one of the allowed values."""

    def get_name(self) -> str:
        return "ENUM"

    def validate(self, ns_node: NodeDefinition, node: Node) -> None:
        if node.is_text_node():
            raise _not_allowed_text(node)
        value = node.get_text()
        if not ns_node.is_allowed_value(value):
            raise ValidationException(node.get_line(), "INVALID_VALUE",
                                      f"The value '{value}' not allowed. Only: {ns_node.get_values()}")


# ---------------------------------------------------------------- regex types

class RegexValue(Type):
    """Base class: INLINE value form only; the value is checked against a pattern."""

    def __init__(self, name: str, pattern: str, error: str) -> None:
        self._name = name
        # ASCII digits only, like the \d of the JS and Java ports
        self._pattern = re.compile(pattern, re.ASCII)
        self._error = error

    def get_name(self) -> str:
        return self._name

    def validate(self, ns_node: NodeDefinition, node: Node) -> None:
        if node.is_text_node():
            raise _not_allowed_text(node)
        value = node.get_text()
        if self._pattern.fullmatch(value) is None:
            raise ValidationException(node.get_line(), "INVALID_VALUE",
                                      f"{node.get_name()}: {self._error} ({value})")


BOOLEAN = RegexValue("BOOLEAN", r"(true|false)", "Invalid boolean")
NUMBER = RegexValue("NUMBER", r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", "Invalid number")
INTEGER = RegexValue("INTEGER", r"[-+]?\d+", "Invalid integer")
# Absolute URL with a mandatory scheme and host, following the grammar of STXT-SCHEMA-SPEC 9.4
# (scheme "://" [userinfo "@"] host [":" port] ["/" path] ["?" query] ["#" fragment]) and not
# urllib, so every port accepts exactly the same values: any scheme of the form letter +
# letters/digits/+/-/., a non-empty host (no TLD required, IPv6 in brackets, non-ASCII kept),
# no inner blanks, numeric port; mailto:/urn:/file:/// and scheme-less values are rejected.
URL = RegexValue("URL",
                 r"[A-Za-z][A-Za-z0-9+.-]*://(?:[^ \t/?#@]+@)?(?:\[[0-9A-Fa-f:.]+\]|[^ \t/?#@:\[\]]+)"
                 r"(?::[0-9]+)?(?:/[^ \t?#]*)?(?:\?[^ \t#]*)?(?:#[^ \t]*)?",
                 "Invalid URL")
NATURAL = RegexValue("NATURAL", r"\d+", "Invalid natural")


# ---------------------------------------------------------------- calendar and clock types

def is_valid_date(year: int, month: int, day: int) -> bool:
    """True if the year-month-day exists in the proleptic Gregorian calendar (year 0000-9999).

    Never ``datetime``: the shape is checked by the regex, the ranges here, like every port.
    """
    if month < 1 or month > 12 or day < 1:
        return False
    leap = (year % 4 == 0 and year % 100 != 0) or year % 400 == 0
    days_in_month = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return day <= days_in_month[month - 1]


def is_valid_time(hour: int, minute: int, second: int) -> bool:
    """True if hour 00-23, minute 00-59, second 00-59 (no leap second)."""
    return hour <= 23 and minute <= 59 and second <= 59


class RangeValue(Type):
    """A value that must match a pattern and whose groups must then pass a range check
    (the calendar and clock types of STXT-SCHEMA-SPEC 9.4). INLINE value form only."""

    def __init__(self, name: str, pattern: str, in_range: "Callable[[re.Match[str]], bool]", error: str) -> None:
        self._name = name
        self._pattern = re.compile(pattern, re.ASCII)
        self._in_range = in_range
        self._error = error

    def get_name(self) -> str:
        return self._name

    def validate(self, ns_node: NodeDefinition, node: Node) -> None:
        if node.is_text_node():
            raise _not_allowed_text(node)
        value = node.get_text()
        m = self._pattern.fullmatch(value)
        if m is None or not self._in_range(m):
            raise ValidationException(node.get_line(), "INVALID_VALUE",
                                      f"{node.get_name()}: {self._error} ({value})")


def _group(m: "re.Match[str]", i: int, fallback: int = 0) -> int:
    return fallback if m.group(i) is None else int(m.group(i))


# YYYY-MM-DD, an existing date of the proleptic Gregorian calendar
DATE = RangeValue("DATE", r"(\d{4})-(\d{2})-(\d{2})",
                  lambda m: is_valid_date(_group(m, 1), _group(m, 2), _group(m, 3)), "Invalid date")
# hh:mm:ss in range (00-23, 00-59, 00-59); no fraction, no zone
TIME = RangeValue("TIME", r"(\d{2}):(\d{2}):(\d{2})",
                  lambda m: is_valid_time(_group(m, 1), _group(m, 2), _group(m, 3)), "Invalid time")
# DATE "T" hh:mm [":" ss ["." digits]] ["Z" | sign hh:mm]; date, time and offset in range;
# seconds, fraction (one or more digits) and zone optional
TIMESTAMP = RangeValue(
    "TIMESTAMP",
    r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|[+-](\d{2}):(\d{2}))?",
    lambda m: (is_valid_date(_group(m, 1), _group(m, 2), _group(m, 3))
               and is_valid_time(_group(m, 4), _group(m, 5), _group(m, 6))
               and (m.group(7) is None or is_valid_time(_group(m, 7), _group(m, 8), 0))),
    "Invalid timestamp")
UUID = RegexValue("UUID", r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                  "Invalid UUID")
# EMAIL, per the normative grammar of STXT-SCHEMA-SPEC 9.4: the bare address (user@domain.tld)
# or a display name followed by the address between angle brackets (Joan Costa <joan@example.com>).
# The display name is any non-empty text without '<' or '>' (quotes are not interpreted) whose
# last character is not a blank, and the blank before '<' is optional; '<'/'>' without a name,
# unbalanced or followed by anything are rejected. ASCII only (no EAI), permissive with dots (the
# full RFC 5322 dot-atom is not replicated), RFC 5321 practical length limits: local part 1-64,
# whole address at most 254, TLD 2-63 letters. Blanks are the STXT ones (U+0020/U+0009) only, so
# no \s here.
# The address proper, local@domain per the normative grammar, as it reads when it ends the value...
_EMAIL_ADDRESS = (r"(?=.{1,254}$)(?=[^@]{1,64}@)"
                  r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}")
# ...and the same address as it reads between '<' and '>' (the lookaheads stop at the '>').
_EMAIL_BRACKETED = (r"(?=[^>]{1,254}>$)(?=[^@>]{1,64}@)"
                    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}")
EMAIL = RegexValue("EMAIL",
                   r"(?:[^<>]*[^<> \t][ \t]*<" + _EMAIL_BRACKETED + r">|" + _EMAIL_ADDRESS + r")",
                   "Invalid email")


# ---------------------------------------------------------------- specific types

class BinaryString(Type):
    """Base class for the binary string types (9.5), in the style of :class:`RegexValue`:
    INLINE or BLOCK form; blanks are removed by :func:`binary_value` and the remaining
    value is checked against a pattern."""

    def __init__(self, name: str, pattern: str, error: str) -> None:
        self._name = name
        self._pattern = re.compile(pattern)
        self._error = error

    def get_name(self) -> str:
        return self._name

    def validate(self, ns_node: NodeDefinition, node: Node) -> None:
        value = binary_value(node)
        if self._pattern.fullmatch(value) is None:
            raise ValidationException(node.get_line(), "INVALID_VALUE",
                                      f"{node.get_name()}: {self._error} ({value})")


# Hexadecimal string [0-9A-Fa-f]+ and string of zeros and ones [01]+ (9.5)
HEXADECIMAL = BinaryString("HEXADECIMAL", r"[0-9A-Fa-f]+", "Invalid hexadecimal")
BINARY = BinaryString("BINARY", r"[01]+", "Invalid binary")


class BASE64(Type):
    """Decodable Base64 content (9.5). INLINE or BLOCK form."""

    def get_name(self) -> str:
        return "BASE64"

    def validate(self, ns_node: NodeDefinition, node: Node) -> None:
        if not is_valid_base64(binary_value(node)):
            raise ValidationException(node.get_line(), "INVALID_VALUE",
                                      f"Node '{node.get_name()}' Invalid Base64")


# ---------------------------------------------------------------- registry

class TypeRegistry:
    """Registry of the supported types (the 19 of STXT-SCHEMA-SPEC), by name."""

    _registry: dict[str, Type] = {}

    @classmethod
    def get(cls, node_type: str) -> Optional[Type]:
        """The type with that name, or ``None`` if it is not supported."""
        return cls._registry.get(node_type)

    @staticmethod
    def admits_children(node_type: str) -> bool:
        """STXT-SCHEMA-SPEC 9.1 / STXT-TEMPLATE-SPEC 8.2: only INLINE and GROUP admit children."""
        return node_type in ("INLINE", "GROUP")

    @classmethod
    def register(cls, instance: Type) -> None:
        """Raises ``TYPE_DUPLICATED`` if a type with that name already exists."""
        if instance.get_name() in cls._registry:
            raise RuntimeException("TYPE_DUPLICATED", "Type already defined: " + instance.get_name())
        cls._registry[instance.get_name()] = instance

    @classmethod
    def names(cls) -> list[str]:
        """The names of the registered types, in registration order."""
        return list(cls._registry.keys())


for _type in (INLINE(), BLOCK(), TEXT(), MARKDOWN(), BOOLEAN, URL, INTEGER, NATURAL, NUMBER, DATE,
              TIME, TIMESTAMP, UUID, EMAIL, HEXADECIMAL, BINARY, BASE64(), GROUP(), ENUM()):
    TypeRegistry.register(_type)
del _type


__all__ = ["Type", "TypeRegistry", "RegexValue", "RangeValue", "BinaryString", "binary_value"]
