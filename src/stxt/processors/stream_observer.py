"""StreamObserver: process hook notified by the parser with the stream of results
(``stxt-impl/processors/stream_observer.txt``)."""

from __future__ import annotations

from ..core.node import Node
from ..exceptions import ParseException


class StreamObserver:
    """Notified with the stream of results a parse emits: each completed root node, and every
    error.

    It complements :class:`Observer`, which watches the process line by line: a StreamObserver
    only sees finished roots and errors, so a consumer that processes a document root by root
    never has to ask a node for its level. Register it with
    :meth:`Parser.register_stream_observer`; a class may subclass :class:`Observer`,
    StreamObserver or both. Subclass it and override the callbacks you need (the defaults do
    nothing). StreamObservers must not modify the nodes they receive.

    It fires in every entry point -- ``parse()``, ``parse_result()`` and ``parse_stream()`` --
    exactly the same way; what ``parse_stream()`` adds is that the parser retains nothing, so
    there these callbacks are the only way to get the results.
    """

    def on_root_node(self, node: Node) -> None:
        """Called when a root (level 0) node is closed, with its whole subtree already complete
        -- children, values, text lines -- and its validators already run. In
        :meth:`Parser.parse_stream` the parser releases the node right after this call, so the
        memory in use is one root tree at a time."""

    def on_error(self, error: ParseException) -> None:
        """Called for every error found (syntax or validation), in order of appearance.
        Parsing continues with the next line, except for ``LIMIT_*`` errors
        (:class:`LimitException`, STXT-SPEC 11.2), which abort the parse right after this
        call. In fail-fast :meth:`Parser.parse` the observer still sees every error before the
        first one is raised, because ``parse()`` reuses the ``parse_result()`` traversal."""
