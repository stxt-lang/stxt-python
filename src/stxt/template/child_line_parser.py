"""ChildLineParser: parses the optional RuleSpec of a ``Structure >>`` line
(``stxt-impl/template/child_line_parser.txt``).

The RuleSpec is the part AFTER the ``:`` of a template line::

    [ "(" cardinality ")" ]  [ type | "@Reference" ]  [ "[" ENUM values "]" ]
"""

from __future__ import annotations

import re

from ..core.constants import MAX_CARDINALITY
from ..core.platform import is_natural, parse_integer
from ..core.string_utils import trim
from ..exceptions import ValidationException
from .child_line import ChildLine

# Pattern with three optional groups: count, type, values.
# Only U+0020/U+0009 count as blanks here (TEMPLATE-SPEC 6.2/9): the pattern uses ``[ \t]``
# instead of ``\s`` so that NBSP, U+3000... are treated as content, exactly like the other
# ports. Otherwise the three ports would accept/reject different inputs.
CHILD_LINE_PATTERN = re.compile(
    r"^[ \t]*"
    r"(?:\([ \t]*(?P<count>[^() \t][^)]*?)[ \t]*\)[ \t]*)?"   # (cardinality)
    r"(?P<type>[^()\[\]]*)?"                                    # type or @reference
    r"(?:\[[ \t]*(?P<values>[^\]]*?)[ \t]*\][ \t]*)?"          # [ENUM values]
    r"[ \t]*$"
)


def parse_child_line(raw_line: str, line_number: int) -> ChildLine:
    """Interprets cardinality, type and values of a RuleSpec.

    Raises:
        ValidationException: ``STRUCTURE_LINE_NOT_VALID``, ``CARDINALITY_NOT_VALID``,
            ``MIN_GREATER_THAN_MAX`` or ``VALUE_DUPLICATED``.
    """
    # Line with no RuleSpec: everything defaults
    if trim(raw_line) == "":
        return ChildLine(None, None, None, None)

    matcher = CHILD_LINE_PATTERN.match(raw_line)
    if matcher is None:
        raise ValidationException(line_number, "STRUCTURE_LINE_NOT_VALID", "Line not valid: " + raw_line)

    # --- Type (or @Name reference) ---
    type_ = matcher.group("type")
    if type_ is not None:
        type_ = trim(type_)
    if not type_:
        type_ = None

    # --- Cardinality (STXT-TEMPLATE-SPEC 7.1) ---
    count = trim(matcher.group("count") or "")

    min_ = None
    max_ = None

    if count == "" or count == "*":
        pass                                        # (*) or absent: no limits
    elif count == "?":
        max_ = 1                                    # zero or one
    elif count == "+":
        min_ = 1                                    # one or more
    elif count.endswith("+"):
        min_ = _parse_count(count[:-1], count, raw_line, line_number)   # num+ : num or more
    elif "," in count:
        parts = count.split(",")
        if len(parts) != 2:
            raise ValidationException(line_number, "CARDINALITY_NOT_VALID", f"Invalid count {count} in line: {raw_line}")
        min_ = _parse_count(trim(parts[0]), count, raw_line, line_number)
        max_ = _parse_count(trim(parts[1]), count, raw_line, line_number)
        if min_ > max_:
            raise ValidationException(line_number, "MIN_GREATER_THAN_MAX",
                                      f"Min {min_} greater than Max {max_} in line: {raw_line}")
    elif count.endswith("-"):
        max_ = _parse_count(count[:-1], count, raw_line, line_number)   # num- : up to num
    else:
        min_ = _parse_count(count, count, raw_line, line_number)        # exact num
        max_ = min_

    # --- ENUM values ---
    # Brackets being present (even empty ones, "[]") count as an explicit definition of
    # values: a non-None (possibly empty) list, to tell it apart from no brackets at all.
    values = None
    values_str = matcher.group("values")
    if values_str is not None:
        values = []
        parts = values_str.split(",")
        for part in parts:
            part = trim(part)
            # An empty item ("[a, , b]", "[a, b,]") is an error, as an empty Value: is in a
            # schema (STXT-TEMPLATE-SPEC 14.14). Only the whole list may be empty ("[]"),
            # which the template parser reports as VALUES_REQUIRED.
            if part == "" and len(parts) > 1:
                raise ValidationException(line_number, "VALUE_EMPTY", f"Empty ENUM value in {values_str}")
            if part == "":
                continue
            # ENUM values cannot repeat after the trim (14.14)
            if part in values:
                raise ValidationException(line_number, "VALUE_DUPLICATED", f"The values {part} is duplicated")
            values.append(part)

    return ChildLine(type_, min_, max_, values)


def _parse_count(num: str, count: str, raw_line: str, line_number: int) -> int:
    # num, min and max must be NON-NEGATIVE integers, with no trailing text, bounded to
    # 2^32 - 1 like Min/Max in a schema (7.1)
    if not is_natural(num):
        raise ValidationException(line_number, "CARDINALITY_NOT_VALID", f"Invalid count {count} in line: {raw_line}")
    value = parse_integer(num)
    if value > MAX_CARDINALITY:
        raise ValidationException(line_number, "CARDINALITY_NOT_VALID", f"Invalid count {count} in line: {raw_line}")
    return value


__all__ = ["parse_child_line", "CHILD_LINE_PATTERN"]
