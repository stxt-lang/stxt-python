"""NodeWriter: serializes a Node (or a list of root nodes) back to STXT text
(``stxt-impl/core/node_writer.txt``).

ROUND-TRIP GUARANTEE: writing a parsed tree and re-parsing the output produces the same
logical tree. The source text is not preserved verbatim: comments are gone, whitespace is
normalized and the namespace is written where the node DECLARES it; inherited namespaces are
implicit.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from ..core.node import InlineNode, Node, TextNode
from ..core.string_utils import is_empty


class IndentStyle(str, Enum):
    """Indentation styles of the writer."""

    TABS = "TABS"            #: one tab character per level
    SPACES_4 = "SPACES_4"    #: four spaces per level


class NodeWriter:
    """Static serializer of nodes to STXT text."""

    @staticmethod
    def to_stxt(node: Node, style: IndentStyle = IndentStyle.TABS) -> str:
        """Serializes a node (along with its children) to STXT text."""
        out: list[str] = []
        NodeWriter._write_node(out, node, 0, style, "")
        return "".join(out)

    @staticmethod
    def to_stxt_docs(docs: Iterable[Node], style: IndentStyle = IndentStyle.TABS) -> str:
        """Serializes a list of root nodes to STXT text, separated by a blank line."""
        out: list[str] = []
        first = True
        for doc in docs:
            if not first:
                out.append("\n")
            first = False
            NodeWriter._write_node(out, doc, 0, style, "")
        return "".join(out)

    @staticmethod
    def _write_node(out: list[str], n: Node, depth: int, style: IndentStyle, parent_ns: str) -> None:
        """Writes one node and its children in the canonical text form of STXT-TREE-SPEC 11.1.
        ``parent_ns`` is the effective namespace of the parent, "" for a root: the namespace is
        declared only where it changes (rule 3), wherever the source declared it."""
        NodeWriter._write_indent(out, depth, style)

        ns = n.get_namespace()
        out.append(n.get_name())
        if ns != parent_ns:
            out.append(f" ({ns})")

        if isinstance(n, TextNode):
            out.append(" >>\n")
            # Block lines are written one level deeper than the node
            for text_line in n.get_text_lines():
                NodeWriter._write_indent(out, depth + 1, style)
                out.append(text_line + "\n")
        else:
            assert isinstance(n, InlineNode)
            out.append(":")
            value = n.get_value()
            if not is_empty(value):
                out.append(" " + value)
            out.append("\n")
            for child in n.get_children():
                NodeWriter._write_node(out, child, depth + 1, style, ns)

    @staticmethod
    def _write_indent(out: list[str], depth: int, style: IndentStyle) -> None:
        if depth == 0:
            return
        unit = "    " if style == IndentStyle.SPACES_4 else "\t"
        out.append(unit * depth)


__all__ = ["IndentStyle", "NodeWriter"]
