"""Observer: process hook notified by the parser while parsing, in streaming
(``stxt-impl/processors/observer.txt``)."""

from __future__ import annotations

from ..core.line_indent import LineIndent
from ..core.node import Node, TextNode


class Observer:
    """Notified when each node is opened and closed, and for every comment and text line.

    Register it with :meth:`Parser.register_observer`. Subclass it and override the callbacks
    you need (the defaults do nothing). Observers must not modify the nodes they receive.
    """

    def on_create(self, node: Node, line_string: str) -> None:
        """Called when a node is opened (its children and text lines are not complete yet).
        The node is already attached to its parent, so ``get_parent()``, the effective
        namespace and ``get_level()`` are available."""

    def on_finish(self, node: Node) -> None:
        """Called when a node is closed, with all its children and its value complete."""

    def on_comment(self, line_number: int, line_string: str) -> None:
        """Called for every comment line, which produces no node."""

    def on_text_line(self, node: TextNode, line_number: int, line_string: str,
                     line_indent: LineIndent) -> None:
        """Called for every text line appended to an open BLOCK node."""
