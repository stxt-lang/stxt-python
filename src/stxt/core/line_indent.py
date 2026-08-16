"""LineIndent and parse_line: a source line split into indentation and content
(``stxt-impl/core/line_indent.txt``; STXT-SPEC sections 8, 10.2, 10.3 and 11)."""

from __future__ import annotations

from ..exceptions import ParseException
from .constants import COMMENT_CHAR, SPACE, TAB, TAB_SPACES
from .string_utils import right_trim


class LineIndent:
    """A source line already split into its indentation and its content.

    It is what tells the parser whether the line opens a node, continues a text block or is
    just a comment.

    Attributes:
        indent_level: indentation level of the line.
        line_without_indent: content with the indentation already removed.
        is_comment: True if the line is a comment (``#``).
        is_block: True if the line is a text line of an open BLOCK node (``>>``).
        indent_length: number of characters the indentation took up.
    """

    __slots__ = ("indent_level", "line_without_indent", "is_comment", "is_block", "indent_length")

    def __init__(self, indent_level: int, line_without_indent: str, is_comment: bool,
                 is_block: bool, indent_length: int) -> None:
        self.indent_level = indent_level
        self.line_without_indent = line_without_indent
        self.is_comment = is_comment
        self.is_block = is_block
        self.indent_length = indent_length

    def is_empty(self) -> bool:
        """True if the line has no content beyond whitespace."""
        return self.line_without_indent.strip() == ""

    def __repr__(self) -> str:
        return (f"LineIndent(level={self.indent_level}, content={self.line_without_indent!r}, "
                f"comment={self.is_comment}, block={self.is_block}, indent_length={self.indent_length})")


def parse_line(line: str, last_node_block: bool, last_level: int, num_line: int) -> LineIndent:
    """Splits a source line into indentation and content, applying the indentation rules.

    * 1 level = 1 TAB or ``TAB_SPACES`` spaces.
    * The indentation of a single line must be homogeneous (only tabs or only spaces);
      mixing both is ``MIXED_INDENTATION``.
    * Comment lines and empty lines are never an error: their indentation is not validated.

    Args:
        line: the raw source line (without its line break).
        last_node_block: True if the node currently open is a BLOCK (``>>``) node.
        last_level: level of the node currently open (0 when none).
        num_line: 1-based line number, for the errors.

    Raises:
        ParseException: ``MIXED_INDENTATION``, ``INVALID_NUMBER_SPACES`` or
            ``INDENTATION_LEVEL_NOT_VALID``.
    """
    level = 0
    spaces = 0
    pointer = 0
    saw_space = False
    saw_tab = False
    length = len(line)

    while pointer < length:
        c = line[pointer]

        if c == SPACE:
            saw_space = True
            spaces += 1
            if spaces == TAB_SPACES:
                level += 1
                spaces = 0

        elif c == TAB:
            saw_tab = True
            level += 1
            spaces = 0

        elif c == COMMENT_CHAR:
            # Comment line: produces no node; its indentation is NOT validated (section 11).
            return LineIndent(level, line[pointer + 1:], True, False, pointer)

        else:
            # First non space/tab/comment character: end of indentation
            break

        # Inside a text block: the line belongs to the block as soon as its level goes
        # beyond the level of the block node. The rest of the line is free text: only
        # right trim is applied (section 10.2).
        if last_node_block and level > last_level:
            text = right_trim(line[pointer + 1:])

            # The prefix covering the block level must be homogeneous (10.2 rule 1).
            # Empty lines are always preserved and exempt from the check (10.3).
            if saw_space and saw_tab and len(text) > 0:
                raise ParseException(num_line, "MIXED_INDENTATION", "Mixed tabs and spaces in indentation")

            return LineIndent(level, text, False, True, pointer)

        pointer += 1

    # At this point we are outside a text block (if any)

    # Empty or whitespace-only line
    if pointer == length:
        if last_node_block:
            # Empty lines inside a block are preserved as "" (section 10.3)
            return LineIndent(level, "", False, True, pointer)
        # Empty lines outside a block are ignored; indentation not validated (section 11)
        return LineIndent(level, "", False, False, pointer)

    # Mixed tabs and spaces in the indentation of the same line (sections 8.1, 8.3)
    if saw_space and saw_tab:
        raise ParseException(num_line, "MIXED_INDENTATION", "Mixed tabs and spaces in indentation")

    # Invalid indentation: spaces not a multiple of TAB_SPACES
    if spaces > 0:
        raise ParseException(num_line, "INVALID_NUMBER_SPACES", f"There are {spaces} spaces before node")

    # Validate indentation level progression (no jumps, section 11.3)
    if level > last_level + 1:
        raise ParseException(num_line, "INDENTATION_LEVEL_NOT_VALID", f"Level of indent incorrect: {level}")

    # General case: return the line without the consumed indentation
    return LineIndent(level, line[pointer:].strip(), False, False, pointer)
