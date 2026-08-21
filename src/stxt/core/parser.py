"""Parser: line-by-line STXT parsing engine (``stxt-impl/core/parser.txt``).

It knows nothing about schemas: semantic validation is plugged in through
:meth:`Parser.register_validator` and observation through :meth:`Parser.register_observer`.

Algorithm: a stack of open nodes, one per indentation level. When a line at level N arrives,
every node deeper than N is closed (validated and notified to the observers), and the new
node is created, ATTACHED to its parent (or added to the documents if it is a root) and
pushed onto the stack, still open. A document may hold multiple root nodes.

Two modes: :meth:`Parser.parse` (fail-fast, raises the first error) and
:meth:`Parser.parse_result` (multi-error, collects every error in a :class:`ParseResult`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..exceptions import ParseException
from .constants import SEP_NODE, SEP_TEXT_NODE
from .line_indent import LineIndent, parse_line
from .name_namespace import parse_name_namespace
from .node import InlineNode, Node, TextNode
from .parse_result import ParseResult
from .platform import split_lines
from .string_utils import remove_utf8_bom, trim

if TYPE_CHECKING:  # pragma: no cover
    from ..processors.observer import Observer
    from ..processors.validator import Validator


class Parser:
    """The STXT parser. Create one, optionally register observers/validators, and parse."""

    def __init__(self) -> None:
        self._observers: list["Observer"] = []
        self._validators: list["Validator"] = []

    def register_observer(self, observer: "Observer") -> None:
        """Registers an observer, notified when each node is opened and closed, and for every
        comment and text line."""
        self._observers.append(observer)

    def register_validator(self, validator: "Validator") -> None:
        """Registers a validator, invoked when each node is closed."""
        self._validators.append(validator)

    def parse(self, content: str) -> list[Node]:
        """Fail-fast mode: parses the content and returns its root nodes.

        Raises:
            ParseException: the first error found (syntax or validation).
        """
        result = self.parse_result(content)
        if result.has_errors():
            raise result.get_errors()[0]
        return result.get_nodes()

    def parse_result(self, content: str) -> ParseResult:
        """Multi-error mode: parses the whole content collecting every error found (both syntax
        and validation) without bailing out on the first one."""
        content = remove_utf8_bom(content)

        result = ParseResult()
        stack: list[Node] = []
        documents: list[Node] = []

        lines = split_lines(content)

        # The final line break terminates the last line, it is not an extra empty line
        # (this avoids adding a spurious line to a '>>' block at EOF, STXT-SPEC 10.3)
        if lines and lines[-1] == "":
            lines.pop()

        for line_number, line in enumerate(lines, start=1):
            self._process_line(line, line_number, stack, documents, result)

        # Close every node still open at EOF
        self._close_to_level(stack, 0, result)

        for doc in documents:
            result.add_node(doc)

        return result

    def _process_line(self, line_string: str, line_number: int, stack: list[Node],
                      documents: list[Node], result: ParseResult) -> None:
        try:
            last_node = stack[-1] if stack else None

            # One open node per level: the top of the stack is at level size - 1
            last_level = len(stack) - 1 if last_node is not None else 0

            last_node_block = isinstance(last_node, TextNode)

            line_indent = parse_line(line_string, last_node_block, last_level, line_number)

            # Comment line: produces no node. Its indentation was already validated by
            # parse_line like a node's (STXT-SPEC 9), but it never becomes the reference
            # level: last_level is only updated by nodes. A comment at the level of an open
            # block node (or shallower) closes the block (6.1 and 9.1): a block is a literal
            # and cannot be commented from inside. Only the block closes; the comment does
            # not touch the rest of the hierarchy.
            if line_indent.is_comment:
                if last_node_block:
                    self._close_to_level(stack, len(stack) - 1, result)
                for observer in self._observers:
                    observer.on_comment(line_number, line_string)
                return

            # Text line of an open BLOCK node: append it instead of creating a node
            if line_indent.is_block:
                text_node = last_node
                assert isinstance(text_node, TextNode)
                text_node.add_text_line(line_indent.line_without_indent)
                for observer in self._observers:
                    observer.on_text_line(text_node, line_number, line_string, line_indent)
                return

            # Empty lines outside a block are ignored
            if line_indent.is_empty():
                return

            current_level = line_indent.indent_level

            # Close nodes down to the current level (finalizes them)
            self._close_to_level(stack, current_level, result)

            # Create the new node, attach it to its parent (or to the documents if it is a
            # root) and keep it open on the stack. The parent is always an InlineNode: a
            # TextNode on top of the stack only takes text lines, and any line at its level
            # or shallower has just closed it.
            node = create_node(line_indent, line_number)

            if not stack:
                documents.append(node)
            else:
                parent = stack[-1]
                assert isinstance(parent, InlineNode)
                parent.add_child(node)

            for observer in self._observers:
                observer.on_create(node, line_string)

            stack.append(node)

        except ParseException as pe:
            result.add_error(pe)
        except Exception as e:  # noqa: BLE001 - unexpected platform error, collected
            result.add_error(ParseException(line_number, "UNEXPECTED_ERROR", str(e)))

    def _close_to_level(self, stack: list[Node], target_level: int, result: ParseResult) -> None:
        # Closes every node deeper than target_level: runs the validators over it and
        # notifies the observers. (The node was attached to its parent when created.)
        while len(stack) > target_level:
            completed = stack.pop()

            # Validators return errors, they do not throw
            for validator in self._validators:
                try:
                    for error in validator.validate(completed):
                        result.add_error(error)
                except ParseException as pe:
                    result.add_error(pe)
                except Exception as e:  # noqa: BLE001 - a validator that throws does not abort the parse
                    result.add_error(ParseException(completed.get_line(), "UNEXPECTED_ERROR", str(e)))

            for observer in self._observers:
                observer.on_finish(completed)


def create_node(line_indent: LineIndent, line_number: int) -> Node:
    """Builds the node a line opens, telling apart the INLINE form (``Name: value``) from the
    BLOCK one (``Name >>``). The node gets the namespace the LINE declares, if any;
    inheritance from the parent is resolved by the node itself once attached.

    Raises:
        ParseException: ``INVALID_LINE``, ``BLOCK_VALUE_NOT_ALLOWED``, ``INVALID_NAMESPACE``
            or ``INVALID_NODE_NAME``.
    """
    line = line_indent.line_without_indent

    node_index = line.find(SEP_NODE)
    text_index = line.find(SEP_TEXT_NODE)

    if node_index == -1 and text_index == -1:
        raise ParseException(line_number, "INVALID_LINE", "Line not valid: " + line)
    if node_index == -1:
        is_text_node = True
    elif text_index == -1:
        is_text_node = False
    elif node_index < text_index:
        is_text_node = False
    else:
        raise ParseException(line_number, "INVALID_LINE", "Line not valid: " + line)

    if is_text_node:
        name = line[:text_index]
        value = line[text_index + len(SEP_TEXT_NODE):]
    else:
        name = line[:node_index]
        value = line[node_index + len(SEP_NODE):]

    # A '>>' node cannot carry significant inline content on the same line (11.4)
    if is_text_node and trim(value) != "":
        raise ParseException(line_number, "BLOCK_VALUE_NOT_ALLOWED", "Line not valid: " + line)

    # The namespace the line declares, if any ("" when it inherits)
    nn = parse_name_namespace(name, None, line_number, line)
    name = nn.get_name()
    namespace = nn.get_namespace()

    if name == "":
        raise ParseException(line_number, "INVALID_LINE", "Line not valid: " + line)

    if is_text_node:
        return TextNode(name, namespace, None, line_number)
    return InlineNode(name, namespace, value, line_number)


__all__ = ["Parser", "create_node"]
