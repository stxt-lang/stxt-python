"""ParseResult: result of a parse in multi-error mode (``stxt-impl/core/parse_result.txt``)."""

from __future__ import annotations

from ..exceptions import ParseException
from .node import Node


class ParseResult:
    """Collects the root nodes obtained and every error found (both syntax and validation
    ones), without bailing out on the first one. See :meth:`Parser.parse_result`."""

    def __init__(self) -> None:
        self._nodes: list[Node] = []
        self._errors: list[ParseException] = []

    def get_nodes(self) -> list[Node]:
        """Root nodes collected so far."""
        return self._nodes

    def get_errors(self) -> list[ParseException]:
        """Syntax or validation errors collected so far, in order of appearance."""
        return self._errors

    def has_errors(self) -> bool:
        return len(self._errors) > 0

    def add_error(self, error: ParseException) -> None:
        """Adds an error found while parsing, without aborting the traversal."""
        self._errors.append(error)

    def add_node(self, node: Node) -> None:
        """Adds an already closed root node to the result."""
        self._nodes.append(node)
