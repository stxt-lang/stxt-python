"""TreeJson: canonical JSON representation of parsed STXT documents (STXT-TREE-SPEC;
``stxt-impl/core/tree_json.txt``).

The representation describes the logical tree, not the source file: it excludes line/level
metadata, comments, indentation style and derived fields. The outer JSON value is always an
array because a document can have several root nodes.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from ..core.node import InlineNode, Node, TextNode


def to_canonical_node(node: Node) -> dict[str, Any]:
    """The canonical data model of one node (and, for an inline node, its descendants)."""
    if isinstance(node, TextNode):
        return {
            "name": node.get_name(),
            "canonicalName": node.get_canonical_name(),
            "namespace": node.get_namespace(),          # effective
            "form": "block",
            "lines": list(node.get_text_lines()),        # exact copy, empty lines included
        }
    assert isinstance(node, InlineNode)
    return {
        "name": node.get_name(),
        "canonicalName": node.get_canonical_name(),
        "namespace": node.get_namespace(),              # effective
        "form": "inline",
        "value": node.get_value(),
        "children": [to_canonical_node(child) for child in node.get_children()],
    }


def to_canonical_tree(docs: Iterable[Node]) -> list[dict[str, Any]]:
    """Converts all root nodes of a parsed document to the canonical JSON data model."""
    return [to_canonical_node(node) for node in docs]


def to_canonical_json(docs: Iterable[Node]) -> str:
    """The canonical tree serialized as JSON text (two-space indentation, non-ASCII kept)."""
    return json.dumps(to_canonical_tree(docs), indent=2, ensure_ascii=False)


__all__ = ["to_canonical_node", "to_canonical_tree", "to_canonical_json"]
