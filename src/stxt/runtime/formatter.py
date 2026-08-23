"""Reformatting of an STXT document (STXT-TREE-SPEC 12, ``stxt-impl/core/formatter.txt``).

:class:`Formatter` reformats a document **line by line, over the original text**, so that
nothing the parse tree does not hold — comments, blank lines, the exact content of text
blocks — is lost. This is what distinguishes it from :class:`~stxt.NodeWriter`, which writes the
canonical text form of the tree and therefore drops comments and blank lines.

The rules, the same for every tool of the ecosystem:

- A line that **opens a node** is rendered in canonical form: the indentation of its level in
  the requested style, the name as parsed, the namespace only where the source wrote it (a
  child repeating its parent's namespace is redundant but legal, and dropping it would be an
  edit, not a reformat), ``: value`` with exactly one space — or a bare ``:`` when there is no
  value — or `` >>`` for a block.
- A **text line of a block** gets the indentation of the block (its level plus one) in the
  requested style, followed by its content; any indentation the line had beyond the block's is
  content (STXT-SPEC 10.2) and is kept exactly. A blank line of the block is ``""`` in the
  content (STXT-SPEC 10.3), so it is written with the indentation of the block too.
- Every **other line** — a comment, a blank line outside a block, or a line the parse tree does
  not describe because of a syntax error — is kept as the author wrote it, except that its
  trailing blanks are removed and the whole indentation units at its start are converted one
  for one to the requested style (a tab or four spaces in either style count as a unit;
  whatever follows the last whole unit, a remainder included, is kept as it is).

The result is idempotent, round-trips between the two styles, and produces the same canonical
tree as the source; the line ending is kept (CRLF if the source holds any), a final newline only
where the source had one, and an initial BOM is removed. The document is parsed without any
schema: formatting has nothing to do with validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from ..core.line_indent import LineIndent
from ..core.node import InlineNode, Node, TextNode
from ..core.parser import Parser
from ..core.string_utils import right_trim
from ..exceptions import ParseException
from ..processors.observer import Observer
from .node_writer import IndentStyle

_EOL = re.compile(r"\r?\n")


@dataclass(frozen=True)
class FormatResult:
    """The outcome of :meth:`Formatter.format`.

    ``text`` is the formatted document: the same lines as the source, in the same order, with
    the same line ending (CRLF is kept) and with a final newline only where the source had one.
    ``errors`` are the syntax errors found while parsing, in line order; empty when the document
    parses. Formatting never repairs a document, and whether a document with errors should be
    reformatted at all is the caller's decision.
    """

    text: str
    errors: list[ParseException]


@dataclass(frozen=True)
class _TextLine:
    node: TextNode
    line: LineIndent


class _SourceLines(Observer):
    """The parse of a document seen as source lines: which line opened which node, and which
    line is a text line of which block."""

    def __init__(self) -> None:
        self.node_by_line: dict[int, Node] = {}
        self.text_by_line: dict[int, _TextLine] = {}

    def on_create(self, node: Node, line_string: str) -> None:
        self.node_by_line[node.get_line()] = node

    def on_finish(self, node: Node) -> None:
        pass  # formatting only needs to know where each node started

    def on_comment(self, line_number: int, line_string: str) -> None:
        pass  # every line that opens no node is treated alike

    def on_text_line(self, node: TextNode, line_number: int, line_string: str, line_indent: LineIndent) -> None:
        self.text_by_line[line_number] = _TextLine(node, line_indent)


class Formatter:
    """Reformats STXT documents; see the module docstring. Not instantiable."""

    def __init__(self) -> None:
        raise TypeError("Formatter is a namespace of static methods")

    @staticmethod
    def format(text: str, style: IndentStyle = IndentStyle.TABS) -> FormatResult:
        """Formats a document.

        Args:
            text: the document.
            style: indentation style to format with; tabs by default.

        Returns:
            the formatted text and the syntax errors found; see :class:`FormatResult`.
        """
        # STXT-TREE-SPEC 12.1: an initial BOM is not kept
        if text.startswith("﻿"):
            text = text[1:]

        source_lines = _SourceLines()
        parser = Parser()
        parser.register_observer(source_lines)
        result = parser.parse_result(text)

        eol = "\r\n" if "\r\n" in text else "\n"
        lines = _EOL.split(text)
        formatted = eol.join(Formatter._format_line(line, index + 1, style, source_lines)
                             for index, line in enumerate(lines))
        return FormatResult(formatted, list(result.get_errors()))

    @staticmethod
    def _format_line(line: str, line_number: int, style: IndentStyle, source_lines: _SourceLines) -> str:
        node = source_lines.node_by_line.get(line_number)
        if node is not None:
            return Formatter._render_node(node, line, style)
        text = source_lines.text_by_line.get(line_number)
        if text is not None:
            return Formatter._indent(text.node.get_level() + 1, style) + text.line.line_without_indent
        return Formatter._convert_units(right_trim(line), style)

    @staticmethod
    def _render_node(node: Node, line: str, style: IndentStyle) -> str:
        """The line that opens a node, in canonical form; the source line only tells whether it
        spelled the namespace out."""
        head = line[:line.index(":")] if isinstance(node, InlineNode) else line
        name = f"{node.get_name()} ({node.get_namespace()})" if "(" in head else node.get_name()
        prefix = Formatter._indent(node.get_level(), style)
        if isinstance(node, TextNode):
            return f"{prefix}{name} >>"
        assert isinstance(node, InlineNode)
        value = node.get_value()
        return f"{prefix}{name}: {value}" if value else f"{prefix}{name}:"

    @staticmethod
    def _convert_units(line: str, style: IndentStyle) -> str:
        """Converts the whole indentation units at the start of the line and keeps the rest,
        remainder included."""
        consumed = 0
        units = 0
        unit = Formatter._unit_at(line, consumed)
        while unit > 0:
            consumed += unit
            units += 1
            unit = Formatter._unit_at(line, consumed)
        return line if units == 0 else Formatter._indent(units, style) + line[consumed:]

    @staticmethod
    def _unit_at(line: str, position: int) -> int:
        """Length of the whole indentation unit — a tab or four spaces — at ``position``, or 0."""
        if line.startswith("\t", position):
            return 1
        return 4 if line.startswith("    ", position) else 0

    @staticmethod
    def _indent(level: int, style: IndentStyle) -> str:
        return ("    " if style == IndentStyle.SPACES_4 else "\t") * level


__all__ = ["Formatter", "FormatResult"]
