"""Parser: line-by-line STXT parsing engine (``stxt-impl/core/parser.txt``).

It knows nothing about schemas: semantic validation is plugged in through
:meth:`Parser.register_validator`, process observation through
:meth:`Parser.register_observer` and result observation through
:meth:`Parser.register_stream_observer`.

Algorithm: a stack of open nodes, one per indentation level. When a line at level N arrives,
every node deeper than N is closed (validated and notified to the observers), and the new
node is created, ATTACHED to its parent (or kept as a root if the stack is empty) and
pushed onto the stack, still open. A document may hold multiple root nodes.

Three entry points share one traversal: :meth:`Parser.parse` (fail-fast, raises the first
error), :meth:`Parser.parse_result` (multi-error, collects every error in a
:class:`ParseResult`) and :meth:`Parser.parse_stream` (lines in, nothing retained). Which
callbacks fire never depends on the entry point, only on what is registered.

The parser aborts on inputs that exceed its limits (STXT-SPEC 11.2), set to the
``DEFAULT_MAX_*`` values of ``constants`` unless configured through the ``max_*`` keyword
arguments. A limit error is a :class:`LimitException` and is in every case the last one
emitted: the nodes still open are not closed nor notified.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional

from ..exceptions import LimitException, ParseException
from .constants import (
    DEFAULT_MAX_INPUT_SIZE,
    DEFAULT_MAX_LINE_LENGTH,
    DEFAULT_MAX_NESTING,
    SEP_NODE,
    SEP_TEXT_NODE,
)
from .line_indent import LineIndent, parse_line
from .name_namespace import parse_name_namespace
from .node import InlineNode, Node, TextNode
from .parse_result import ParseResult
from .platform import split_lines
from .string_utils import remove_utf8_bom, trim

if TYPE_CHECKING:  # pragma: no cover
    from ..processors.observer import Observer
    from ..processors.stream_observer import StreamObserver
    from ..processors.validator import Validator


class Parser:
    """The STXT parser. Create one, optionally register observers/validators, and parse.

    Keyword Args:
        max_nesting: maximum open nesting levels (level 0 is the first); -1 disables the
            limit. Default ``DEFAULT_MAX_NESTING``.
        max_line_length: maximum length of one input line, indentation included; -1 disables
            the limit. Default ``DEFAULT_MAX_LINE_LENGTH``.
        max_input_size: maximum total input consumed; -1 disables the limit. Default
            ``DEFAULT_MAX_INPUT_SIZE``.
    """

    def __init__(self, *, max_nesting: int = DEFAULT_MAX_NESTING,
                 max_line_length: int = DEFAULT_MAX_LINE_LENGTH,
                 max_input_size: int = DEFAULT_MAX_INPUT_SIZE) -> None:
        self._observers: list["Observer"] = []
        self._stream_observers: list["StreamObserver"] = []
        self._validators: list["Validator"] = []
        self._max_nesting = max_nesting
        self._max_line_length = max_line_length
        self._max_input_size = max_input_size

    def register_observer(self, observer: "Observer") -> None:
        """Registers an observer, notified when each node is opened and closed, and for every
        comment and text line."""
        self._observers.append(observer)

    def register_stream_observer(self, stream_observer: "StreamObserver") -> None:
        """Registers a stream observer, notified with each completed root node and each
        error, in every mode."""
        self._stream_observers.append(stream_observer)

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
        and validation) without bailing out on the first one -- except a
        :class:`LimitException`, which aborts and is in every case the last error collected."""
        result = ParseResult()

        lines = split_lines(content)

        # The final line break terminates the last line, it is not an extra empty line
        # (this avoids adding a spurious line to a '>>' block at EOF, STXT-SPEC 10.3)
        if lines and lines[-1] == "":
            lines.pop()

        self._parse_lines(lines, result)

        return result

    def parse_stream(self, lines: Iterable[str]) -> None:
        """Streaming mode: input from a line iterable (each item one line, without its line
        break -- e.g. a file object read lazily, or a generator), and nothing retained: no
        nodes, no errors. Results reach the program only through the registered
        :class:`StreamObserver` s (each completed root by ``on_root_node()``, each error by
        ``on_error()``), so memory holds one root tree at a time. This is the entry point for
        files that do not fit in memory. The trailing line break of each item, if present, is
        removed, so a file object opened in text mode works as it is."""
        self._parse_lines((_without_line_break(line) for line in lines), None)

    def _parse_lines(self, lines: Iterable[str], result: Optional[ParseResult]) -> None:
        # Shared traversal. With a result, roots and errors are collected into it
        # (parse/parse_result); with None, nothing is retained (parse_stream). Either way
        # every registered callback fires the same.
        stack: list[Node] = []
        consumed = 0

        for line_number, line in enumerate(lines, start=1):
            # A UTF-8 BOM only means anything at the very start of the input (STXT-SPEC 3)
            if line_number == 1:
                line = remove_utf8_bom(line)

            # Limits first (STXT-SPEC 11.2): a limit error aborts, leaving the open nodes
            # unclosed and unnotified.
            if self._max_line_length != -1 and len(line) > self._max_line_length:
                self._emit_error(LimitException(
                    line_number, "LIMIT_LINE_LENGTH_EXCEEDED",
                    f"Line longer than {self._max_line_length} characters"), result)
                return

            consumed += len(line) + 1  # the line separator counts as one
            if self._max_input_size != -1 and consumed > self._max_input_size:
                self._emit_error(LimitException(
                    line_number, "LIMIT_INPUT_SIZE_EXCEEDED",
                    f"Input larger than {self._max_input_size} characters"), result)
                return

            if not self._process_line(line, line_number, stack, result):
                return  # a limit aborted the parse; its error is already emitted

        # Close every node still open at EOF
        self._close_to_level(stack, 0, result)

    def _process_line(self, line_string: str, line_number: int, stack: list[Node],
                      result: Optional[ParseResult]) -> bool:
        # Processes one source line. Errors of this line are collected into the result and
        # the traversal continues with the next line: returns True to keep going, False when
        # a limit aborted the parse (its error is already emitted) -- _parse_lines stops on it.
        try:
            last_node = stack[-1] if stack else None

            # One open node per level: the top of the stack is at level size - 1
            # With no open node the reference level is -1 (spec 8.3): the first line of the
            # document, and the first after every node has been closed, must be at level 0.
            last_level = len(stack) - 1 if last_node is not None else -1

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
                return True

            # Text line of an open BLOCK node: append it instead of creating a node
            if line_indent.is_block:
                text_node = last_node
                assert isinstance(text_node, TextNode)
                text_node.add_text_line(line_indent.line_without_indent)
                for observer in self._observers:
                    observer.on_text_line(text_node, line_number, line_string, line_indent)
                return True

            # Empty lines outside a block are ignored
            if line_indent.is_empty():
                return True

            current_level = line_indent.indent_level

            # Nesting limit (STXT-SPEC 11.2): only a node line can open a new level. Comment
            # and block text lines returned above; with the consecutive-level rule this
            # triggers exactly when the first node at level max_nesting opens.
            if self._max_nesting != -1 and current_level >= self._max_nesting:
                self._emit_error(LimitException(
                    line_number, "LIMIT_NESTING_EXCEEDED",
                    f"Nesting deeper than {self._max_nesting} levels"), result)
                return False

            # Close nodes down to the current level (finalizes them)
            self._close_to_level(stack, current_level, result)

            # Create the new node, attach it to its parent (or keep it as a root if the stack
            # is empty) and keep it open on the stack. The parent is always an InlineNode: a
            # TextNode on top of the stack only takes text lines, and any line at its level
            # or shallower has just closed it.
            node = create_node(line_indent, line_number)

            if stack:
                parent = stack[-1]
                assert isinstance(parent, InlineNode)
                parent.add_child(node)

            for observer in self._observers:
                observer.on_create(node, line_string)

            stack.append(node)

        except ParseException as pe:
            self._emit_error(pe, result)
        except Exception as e:  # noqa: BLE001 - unexpected platform error, collected
            self._emit_error(ParseException(line_number, "UNEXPECTED_ERROR", str(e)), result)

        return True

    def _close_to_level(self, stack: list[Node], target_level: int,
                        result: Optional[ParseResult]) -> None:
        # Closes every node deeper than target_level: runs the validators over it and
        # notifies the observers. (The node was attached to its parent when created.) When
        # the node closed is a root -- the stack is left empty -- the stream observers
        # receive it complete by on_root_node(), and it is collected into the result if
        # there is one (parse/parse_result) or released (parse_stream).
        while len(stack) > target_level:
            completed = stack.pop()

            # A closing block node drops its final empty lines (STXT-SPEC 10.3): they are not
            # content, only visual separation or an editor's final line breaks. The validators
            # and observers below already see the trimmed node; on_text_line did fire for
            # these lines while the block was open, as process observation of the source.
            if isinstance(completed, TextNode):
                completed.remove_trailing_empty_lines()

            # Validators return errors, they do not throw
            for validator in self._validators:
                try:
                    for error in validator.validate(completed):
                        self._emit_error(error, result)
                except ParseException as pe:
                    self._emit_error(pe, result)
                except Exception as e:  # noqa: BLE001 - a validator that throws does not abort the parse
                    self._emit_error(
                        ParseException(completed.get_line(), "UNEXPECTED_ERROR", str(e)), result)

            for observer in self._observers:
                observer.on_finish(completed)

            # A closed root: the stream observers receive it, the result collects it
            if not stack:
                for stream_observer in self._stream_observers:
                    stream_observer.on_root_node(completed)

                if result is not None:
                    result.add_node(completed)

    def _emit_error(self, error: ParseException, result: Optional[ParseResult]) -> None:
        # Every error goes through here: collected into the result when there is one, and
        # notified to the stream observers always, in order of appearance.
        if result is not None:
            result.add_error(error)

        for stream_observer in self._stream_observers:
            stream_observer.on_error(error)


def _without_line_break(line: str) -> str:
    # The trailing line break of one streamed line: "\r\n" or "\n" (a file object opened in
    # text mode with newline="" keeps them; opened by default it yields "\n")
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith("\n"):
        return line[:-1]
    return line


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
