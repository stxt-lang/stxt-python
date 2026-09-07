"""ChildLineParser: parses the optional RuleSpec of a ``Structure >>`` line
(``stxt-impl/template/child_line_parser.txt``).

The RuleSpec is the part AFTER the ``:`` of a template line::

    [ "(" cardinality ")" ]  [ type | "@Reference" ]  [ "[" ENUM values "]" ]
"""

from __future__ import annotations

import re
from typing import Optional

from ..core.constants import MAX_CARDINALITY, MAX_CARDINALITY_DIGITS
from ..core.platform import is_natural, parse_integer
from ..core.string_utils import trim
from ..exceptions import ValidationException
from .child_line import ChildLine

def _is_blank(c: str) -> bool:
    return c == " " or c == "\t"


def _split_rule_spec(raw_line: str) -> Optional[tuple[Optional[str], Optional[str], Optional[str]]]:
    """Splits a RuleSpec ``(count) TYPE [values]`` into its three optional parts by a
    hand-written scan, not a regular expression: the pattern used until 2026-09-06 backtracked
    in O(n^3) on a line without the closing ``]`` (a 10 000-character Structure line took
    minutes). Blanks are U+0020/U+0009 only (TEMPLATE-SPEC 6.2/9), and the rules the pattern
    enforced are kept exactly: the count runs to the first ``)`` and, trimmed, is neither empty
    nor starts with ``(``; the type may not contain ``(``, ``)`` or ``]``; the values run from
    the first ``[`` to the first ``]`` after it, and only blanks may follow that ``]``.

    Returns the trimmed parts (``None`` each when absent), or ``None`` if the line has not
    that shape."""
    n = len(raw_line)
    i = 0
    while i < n and _is_blank(raw_line[i]):
        i += 1

    count: Optional[str] = None
    if i < n and raw_line[i] == "(":
        close = raw_line.find(")", i + 1)
        if close == -1:
            return None
        count = trim(raw_line[i + 1:close])
        if count == "" or count[0] == "(":
            return None
        i = close + 1

    open_ = raw_line.find("[", i)
    type_: Optional[str] = raw_line[i:n if open_ == -1 else open_]
    if "(" in type_ or ")" in type_ or "]" in type_:  # type: ignore[operator]
        return None
    type_ = trim(type_)
    if type_ == "":
        type_ = None

    values: Optional[str] = None
    if open_ != -1:
        close = raw_line.find("]", open_ + 1)
        if close == -1:
            return None
        values = trim(raw_line[open_ + 1:close])
        for j in range(close + 1, n):
            if not _is_blank(raw_line[j]):
                return None

    return count, type_, values


def parse_child_line(raw_line: str, line_number: int) -> ChildLine:
    """Interprets cardinality, type and values of a RuleSpec.

    Raises:
        ValidationException: ``STRUCTURE_LINE_NOT_VALID``, ``CARDINALITY_NOT_VALID``,
            ``MIN_GREATER_THAN_MAX`` or ``VALUE_DUPLICATED``.
    """
    # Line with no RuleSpec: everything defaults
    if trim(raw_line) == "":
        return ChildLine(None, None, None, None)

    rule = _split_rule_spec(raw_line)
    if rule is None:
        raise ValidationException(line_number, "STRUCTURE_LINE_NOT_VALID", "Line not valid: " + raw_line)

    # --- Type (or @Name reference); cardinality (STXT-TEMPLATE-SPEC 7.1) ---
    count_part, type_, values_str = rule
    count = count_part or ""

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
    # A numeral with more digits than MAX_CARDINALITY has exceeds the bound whatever its value:
    # rejected before converting, so int() (limited to 4 300 digits) never gets to raise
    if len(num) > MAX_CARDINALITY_DIGITS:
        raise ValidationException(line_number, "CARDINALITY_NOT_VALID", f"Invalid count {count} in line: {raw_line}")
    value = parse_integer(num)
    if value > MAX_CARDINALITY:
        raise ValidationException(line_number, "CARDINALITY_NOT_VALID", f"Invalid count {count} in line: {raw_line}")
    return value


__all__ = ["parse_child_line"]
