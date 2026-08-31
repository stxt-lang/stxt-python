"""The node model of the STXT tree (``stxt-impl/core/node.txt``).

:class:`Node` is abstract, with exactly two concrete forms (a closed hierarchy):

* :class:`InlineNode` — ``Name: value``: an optional inline value and an ordered list of
  children. The only form with children, and so the only one with child lookups and the
  only one that creates children (``add_inline_node`` / ``add_text_node``).
* :class:`TextNode` — ``Name >>``: an ordered list of literal text lines. No value, no
  children.

Each form owns only what is really its own; ``Node`` keeps what is common: name and
canonical name, declared and effective namespace, source line, parent, ``is_text_node()``
and ``get_text()``. Code that walks a tree asks for the form
(``isinstance(node, InlineNode)``), the same way the canonical tree of STXT-TREE-SPEC has
``children`` only for inline nodes.

Trees are mutable and keep their own integrity: every node knows its parent (always an
``InlineNode``; ``None`` for a root); ``add_child()`` links both ends and refuses a node that
already has a parent (``NODE_ALREADY_ATTACHED``) or that is this node or one of its
ancestors (``NODE_CYCLE``); ``remove_child()`` and ``detach()`` undo it; the level is
derived from the chain of parents, never stored; the source line is optional (``NO_LINE``).

Namespaces: a node stores the namespace it DECLARES (possibly none). Its EFFECTIVE
namespace (``get_namespace()``) is the declared one or, failing that, the effective
namespace of its parent (STXT-SPEC section 7: inherited vertically, never laterally between
roots).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable, Optional, Sequence, Union

from ..exceptions import ParseException, RuntimeException
from .platform import split_lines
from .string_utils import compact_spaces, is_empty, lower_case, normalize_chars, trim_to_not_null
from .validations import is_valid_node_name, validate_namespace_format

#: ``get_line()`` when the node has no known source position.
NO_LINE = -1


class Node(ABC):
    """Abstract base of the two node forms. See the module documentation."""

    #: ``get_line()`` when the node has no known source position.
    NO_LINE = NO_LINE

    __slots__ = ("_name", "_canonical_name", "_declared_namespace", "_line", "_parent")

    def __init_subclass__(cls, **kwargs) -> None:
        # Closed hierarchy: only the two forms defined in this module.
        super().__init_subclass__(**kwargs)
        if cls.__module__ != __name__:
            raise TypeError("Node is a closed hierarchy: only InlineNode and TextNode may extend it")

    def __init__(self, name: str, namespace: Optional[str], line: int) -> None:
        self._parent: Optional["InlineNode"] = None
        self._line = line
        self.set_name(name)
        self.set_namespace(namespace)

    # ---------------------------------------------------------------- name

    def get_name(self) -> str:
        """The name as written, with spaces compacted."""
        return self._name

    def set_name(self, new_name: str) -> None:
        """Renames the node; the canonical name is recomputed.

        Raises:
            ParseException: ``INVALID_NODE_NAME`` if the name is not a valid STXT node name.
        """
        compacted = compact_spaces(new_name)
        if not is_valid_node_name(compacted):
            raise ParseException(self._line, "INVALID_NODE_NAME", f"Node name not valid: {new_name}")
        self._name = compacted
        self._canonical_name = normalize_chars(new_name)

    def get_canonical_name(self) -> str:
        """Canonical name (STXT-SPEC section 4.3), used to compare and look up by identity."""
        return self._canonical_name

    def get_qualified_name(self) -> str:
        """Logical identity: ``effective_namespace:canonical_name`` (just the canonical name if
        there is no namespace). Computed on demand: it follows namespace changes and moves."""
        namespace = self.get_namespace()
        if is_empty(namespace):
            return self._canonical_name
        return f"{namespace}:{self._canonical_name}"

    # ---------------------------------------------------------------- namespace

    def get_declared_namespace(self) -> str:
        """The namespace this node declares itself, lower-cased; ``""`` if it declares none."""
        return self._declared_namespace

    def set_namespace(self, namespace: Optional[str]) -> None:
        """Sets the declared namespace. ``None`` or ``""`` means none: the node then inherits
        its parent's.

        Raises:
            ParseException: ``INVALID_NAMESPACE`` if the format is not valid.
        """
        lower = lower_case(namespace)
        validate_namespace_format(lower, self._line)
        self._declared_namespace = lower

    def get_namespace(self) -> str:
        """Effective namespace: the declared one or, failing that, the parent's effective one;
        ``""`` for a root that declares none."""
        if not is_empty(self._declared_namespace):
            return self._declared_namespace
        if self._parent is not None:
            return self._parent.get_namespace()
        return ""

    # ---------------------------------------------------------------- position

    def get_line(self) -> int:
        """Source line, or :data:`NO_LINE`."""
        return self._line

    def set_line(self, new_line: int) -> None:
        self._line = new_line

    def get_level(self) -> int:
        """Depth in the tree: 0 for a root, 1 for its children... Derived, never stored."""
        level = 0
        p = self._parent
        while p is not None:
            level += 1
            p = p._parent
        return level

    # ---------------------------------------------------------------- tree

    def get_parent(self) -> Optional["InlineNode"]:
        """The parent, or ``None`` for a root node."""
        return self._parent

    def detach(self) -> bool:
        """Removes this node from its parent, if any. Afterwards it is a root and its effective
        namespace is the one it declares. Returns False if it already was a root."""
        if self._parent is None:
            return False
        return self._parent.remove_child(self)

    # ---------------------------------------------------------------- content

    @abstractmethod
    def is_text_node(self) -> bool:
        """True for a :class:`TextNode` (``>>``), False for an :class:`InlineNode`."""

    @abstractmethod
    def get_text(self) -> str:
        """Textual content: the inline value, or the text lines joined with ``\\n``."""

    def __repr__(self) -> str:
        ns = f" ({self._declared_namespace})" if self._declared_namespace else ""
        return f"{type(self).__name__}({self._name}{ns})"


def _apply_positional_args(args: tuple[Any, ...], signature: str, content: Any,
                           namespace: Optional[str], line: int) -> tuple[Any, Optional[str], int]:
    """Emulates the ``(name[, [namespace, ]content[, line]])`` overloads shared by
    :class:`InlineNode` and :class:`TextNode`: with two strings the second is always the
    content, and the namespace only exists in the three-argument form. Positional arguments
    override the keyword defaults; ``signature`` is the message of the ``TypeError`` raised
    on too many of them."""
    if len(args) == 1:
        (content,) = args
    elif len(args) == 2:
        namespace, content = args
    elif len(args) == 3:
        namespace, content, line = args
    elif len(args) > 3:
        raise TypeError(signature)
    return content, namespace, line


class InlineNode(Node):
    """``Name: value``: an optional inline value and an ordered list of children.

    Constructors (the second string is always the CONTENT; the namespace only exists in the
    three-argument form)::

        InlineNode(name)
        InlineNode(name, value)
        InlineNode(name, namespace, value)
        InlineNode(name, namespace, value, line)     # the form the parser uses

    ``value=`` / ``namespace=`` / ``line=`` are also accepted as keywords.
    """

    __slots__ = ("_value", "_children")

    def __init__(self, name: str, *args: Any, value: Optional[str] = None,
                 namespace: Optional[str] = None, line: int = NO_LINE) -> None:
        value, namespace, line = _apply_positional_args(
            args, "InlineNode(name[, [namespace, ]value[, line]])", value, namespace, line)
        self._value = ""
        self._children: list[Node] = []
        super().__init__(name, namespace, line)
        self.set_value(value)

    # ---- value

    def get_value(self) -> str:
        """The inline value, trimmed; ``""`` if none."""
        return self._value

    def set_value(self, new_value: Optional[str]) -> None:
        self._value = trim_to_not_null(new_value)

    def get_text(self) -> str:
        return self._value

    def is_text_node(self) -> bool:
        return False

    # ---- children

    def get_children(self) -> Sequence[Node]:
        """Children in order of appearance, as a read-only view (a tuple)."""
        return tuple(self._children)

    def add_child(self, child: Node, index: Optional[int] = None) -> None:
        """Appends a child (or inserts it at ``index``, 0 = first), linking both ends.

        Raises:
            RuntimeException: ``NODE_ALREADY_ATTACHED`` if the child already has a parent;
                ``NODE_CYCLE`` if it is this node or one of its ancestors.
            IndexError: if ``index`` is out of range.
        """
        if child.get_parent() is not None:
            raise RuntimeException("NODE_ALREADY_ATTACHED",
                                   f"Node '{child.get_name()}' already has a parent: detach it first")

        # Walk up from this node (itself included) looking for the child among the ancestors
        p: Optional[Node] = self
        while p is not None:
            if p is child:
                raise RuntimeException("NODE_CYCLE",
                                       f"Node '{child.get_name()}' cannot be a child of itself or of one of its descendants")
            p = p.get_parent()

        if index is None:
            index = len(self._children)
        elif index < 0 or index > len(self._children):
            raise IndexError(f"Index {index} out of range (0..{len(self._children)})")

        self._children.insert(index, child)
        child._parent = self

    def remove_child(self, child: Node) -> bool:
        """Removes a direct child, unlinking both ends. Identity, not equality. Returns False
        if it was not a direct child of this node."""
        if child.get_parent() is not self:
            return False
        for i, candidate in enumerate(self._children):
            if candidate is child:
                del self._children[i]
                child._parent = None
                return True
        return False

    # ---- lookups (by canonical name + effective namespace)

    def get_child(self, cname: str, child_namespace: Optional[str] = None) -> Optional[Node]:
        """The ONLY direct child with that canonical name in the given effective namespace
        (this node's own when omitted). ``None`` if none.

        Raises:
            RuntimeException: ``AMBIGUOUS_CHILD`` if there are several.
        """
        result = self.get_children_by_name(cname, child_namespace)
        if len(result) > 1:
            raise RuntimeException("AMBIGUOUS_CHILD", "More than 1 child. Use get_children_by_name")
        if not result:
            return None
        return result[0]

    def get_children_by_name(self, cname: str, child_namespace: Optional[str] = None) -> list[Node]:
        """Every direct child with that canonical name in the given effective namespace (this
        node's own when omitted), preserving the order of appearance."""
        if child_namespace is None:
            child_namespace = self.get_namespace()
        key = normalize_chars(cname)
        return [child for child in self._children
                if child.get_canonical_name() == key and child.get_namespace() == child_namespace]

    # ---- factories: create a child, append it, return it

    def add_inline_node(self, name: str, *args: Any, value: Optional[str] = None,
                        namespace: Optional[str] = None) -> "InlineNode":
        """Creates an :class:`InlineNode` child, appends it and returns it. Same argument rule
        as the constructor; a ``None``/``""`` namespace means "inherit this node's"."""
        child = InlineNode(name, *args, value=value, namespace=namespace)
        self.add_child(child)
        return child

    def add_text_node(self, name: str, *args: Any,
                      text: Union[str, Iterable[str], None] = None,
                      namespace: Optional[str] = None) -> "TextNode":
        """Creates a :class:`TextNode` child, appends it and returns it. ``text`` may be a
        string (split into lines at every LF or CRLF) or the lines themselves."""
        child = TextNode(name, *args, text=text, namespace=namespace)
        self.add_child(child)
        return child


class TextNode(Node):
    """``Name >>``: an ordered list of literal text lines. No value, no children.

    Constructors (the second argument is always the CONTENT: a string, split at every LF or
    CRLF — the part after the last break is a line too, possibly empty — or the lines)::

        TextNode(name)
        TextNode(name, text)
        TextNode(name, namespace, text)
        TextNode(name, namespace, text, line)        # the form the parser uses, text=None
    """

    __slots__ = ("_lines",)

    def __init__(self, name: str, *args: Any, text: Union[str, Iterable[str], None] = None,
                 namespace: Optional[str] = None, line: int = NO_LINE) -> None:
        text, namespace, line = _apply_positional_args(
            args, "TextNode(name[, [namespace, ]text[, line]])", text, namespace, line)
        self._lines: list[str] = []
        super().__init__(name, namespace, line)
        self.set_text(text)

    def get_text_lines(self) -> Sequence[str]:
        """Text lines in order, as a read-only view (a tuple)."""
        return tuple(self._lines)

    def set_text(self, text: Union[str, Iterable[str], None]) -> None:
        """Replaces the whole text: a string is split into lines (LF or CRLF); ``None`` empties
        the node; any other iterable is taken as the lines themselves."""
        if text is None:
            self._lines = []
        elif isinstance(text, str):
            self._lines = split_lines(text)
        else:
            self._lines = [str(line) for line in text]

    def set_text_lines(self, new_lines: Iterable[str]) -> None:
        self.set_text(list(new_lines))

    def add_text_line(self, text_line: str) -> None:
        self._lines.append(text_line)

    def clear_text(self) -> None:
        self._lines = []

    def remove_trailing_empty_lines(self) -> None:
        """Removes the final empty lines (``""`` elements at the end of the lines). The parser
        calls it when the block closes (STXT-SPEC 10.3: the final empty lines of a block are
        not content); it is public because a programmatically built node may want the same
        normalization before writing."""
        while self._lines and self._lines[-1] == "":
            self._lines.pop()

    def get_text(self) -> str:
        return "\n".join(self._lines)

    def is_text_node(self) -> bool:
        return True


__all__ = ["NO_LINE", "Node", "InlineNode", "TextNode"]
