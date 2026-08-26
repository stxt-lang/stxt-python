"""Parser limits (STXT-SPEC 11.2) and the StreamObserver / parse_stream pair."""

from __future__ import annotations

import pytest

from stxt import InlineNode, LimitException, Node, Parser, StreamObserver, TextNode
from stxt.exceptions import ParseException


def nested(levels: int) -> str:
    """A document nesting the given number of levels (level 0 is the first)."""
    return "".join("\t" * i + f"N{i}: v\n" for i in range(levels))


class CollectingStreamObserver(StreamObserver):
    """A StreamObserver that collects everything it is notified."""

    def __init__(self) -> None:
        self.roots: list[Node] = []
        self.errors: list[ParseException] = []

    def on_root_node(self, node: Node) -> None:
        self.roots.append(node)

    def on_error(self, error: ParseException) -> None:
        self.errors.append(error)


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

class TestLimits:
    def test_nesting_deeper_than_the_default_100_levels_aborts(self) -> None:
        result = Parser().parse_result(nested(101))

        assert len(result.get_errors()) == 1
        error = result.get_errors()[0]
        assert isinstance(error, LimitException)
        assert error.code == "LIMIT_NESTING_EXCEEDED"
        assert error.line == 101
        # The abort leaves the open nodes unclosed: nothing is collected
        assert result.get_nodes() == []

    def test_nesting_of_exactly_100_levels_parses_under_the_defaults(self) -> None:
        result = Parser().parse_result(nested(100))

        assert result.get_errors() == []
        assert len(result.get_nodes()) == 1

    def test_max_nesting_is_configurable(self) -> None:
        assert not Parser(max_nesting=3).parse_result(nested(3)).has_errors()

        result = Parser(max_nesting=3).parse_result(nested(4))
        assert result.get_errors()[0].code == "LIMIT_NESTING_EXCEEDED"
        assert result.get_errors()[0].line == 4

    def test_max_nesting_minus_one_disables_the_limit(self) -> None:
        result = Parser(max_nesting=-1, max_input_size=-1).parse_result(nested(150))

        assert result.get_errors() == []
        assert len(result.get_nodes()) == 1

    def test_line_longer_than_the_default_10000_characters_aborts(self) -> None:
        result = Parser().parse_result("Name: " + "x" * 10000 + "\n")

        assert len(result.get_errors()) == 1
        assert result.get_errors()[0].code == "LIMIT_LINE_LENGTH_EXCEEDED"
        assert result.get_errors()[0].line == 1

    def test_max_line_length_is_configurable_and_closed_roots_stay_collected(self) -> None:
        content = "First: one\nSecond: two\nThird: " + "x" * 50 + "\n"
        result = Parser(max_line_length=20).parse_result(content)

        assert len(result.get_errors()) == 1
        assert result.get_errors()[0].code == "LIMIT_LINE_LENGTH_EXCEEDED"
        assert result.get_errors()[0].line == 3
        # First closed when line 2 was processed; Second was still open at the abort,
        # because the limit is checked before the line that would have closed it
        assert len(result.get_nodes()) == 1
        assert result.get_nodes()[0].get_name() == "First"

    def test_input_larger_than_max_input_size_aborts(self) -> None:
        result = Parser(max_input_size=30).parse_result(
            "A: 1\nB: 2\nC: 3\nD: 4\nE: 5\nF: 6\nG: 7\n")

        assert len(result.get_errors()) == 1
        assert result.get_errors()[0].code == "LIMIT_INPUT_SIZE_EXCEEDED"

    def test_limit_error_aborts_multi_error_collection_and_is_the_last_error(self) -> None:
        # A syntax error before the limit is collected; the invalid line after it is never seen
        content = "bad line\nName: " + "x" * 50 + "\nalso bad\n"
        result = Parser(max_line_length=20).parse_result(content)

        assert [e.code for e in result.get_errors()] == [
            "INVALID_LINE", "LIMIT_LINE_LENGTH_EXCEEDED"]

    def test_parse_raises_the_limit_error_as_a_limit_exception(self) -> None:
        with pytest.raises(LimitException) as info:
            Parser().parse(nested(101))
        assert info.value.code == "LIMIT_NESTING_EXCEEDED"


# ---------------------------------------------------------------------------
# StreamObserver and parse_stream
# ---------------------------------------------------------------------------

class TestStreamObserver:
    def test_parse_stream_hands_each_completed_root_to_on_root_node(self) -> None:
        def lines():
            yield "Entry: one"
            yield "\tDetail: a"
            yield "Entry: two"
            yield "\tDetail >>"
            yield "\t\ttext line"

        collector = CollectingStreamObserver()
        parser = Parser()
        parser.register_stream_observer(collector)
        parser.parse_stream(lines())

        assert collector.errors == []
        assert len(collector.roots) == 2
        assert collector.roots[0].get_name() == "Entry"
        first = collector.roots[0]
        assert isinstance(first, InlineNode)
        assert len(first.get_children()) == 1
        second = collector.roots[1]
        assert isinstance(second, InlineNode)
        detail = second.get_children()[0]
        assert isinstance(detail, TextNode)
        assert list(detail.get_text_lines()) == ["text line"]

    def test_parse_stream_accepts_lines_with_their_line_break(self) -> None:
        # A file object iterated in text mode yields lines ending in "\n"
        collector = CollectingStreamObserver()
        parser = Parser()
        parser.register_stream_observer(collector)
        parser.parse_stream(["One: 1\n", "Two: 2\n"])

        assert collector.errors == []
        assert [root.get_name() for root in collector.roots] == ["One", "Two"]

    def test_parse_stream_notifies_errors_by_on_error_and_keeps_going(self) -> None:
        collector = CollectingStreamObserver()
        parser = Parser()
        parser.register_stream_observer(collector)
        parser.parse_stream(["bad line", "Name: value"])

        assert [e.code for e in collector.errors] == ["INVALID_LINE"]
        assert len(collector.roots) == 1

    def test_parse_stream_removes_a_bom_on_the_first_line(self) -> None:
        collector = CollectingStreamObserver()
        parser = Parser()
        parser.register_stream_observer(collector)
        parser.parse_stream(["\ufeff" + "Name: value"])

        assert collector.errors == []
        assert collector.roots[0].get_name() == "Name"

    def test_parse_stream_stops_consuming_the_input_when_a_limit_aborts(self) -> None:
        consumed = 0

        def endless():
            nonlocal consumed
            while True:
                consumed += 1
                yield f"Entry: {consumed}"

        collector = CollectingStreamObserver()
        parser = Parser(max_input_size=100)
        parser.register_stream_observer(collector)
        parser.parse_stream(endless())

        assert [e.code for e in collector.errors] == ["LIMIT_INPUT_SIZE_EXCEEDED"]
        assert consumed <= 12, f"the endless input stopped being consumed: {consumed}"

    def test_stream_observer_fires_in_parse_result_too_with_the_same_roots(self) -> None:
        collector = CollectingStreamObserver()
        parser = Parser()
        parser.register_stream_observer(collector)
        result = parser.parse_result("One: 1\nbad line\nTwo: 2\n")

        assert len(collector.roots) == 2
        assert collector.roots[0] is result.get_nodes()[0]
        assert collector.roots[1] is result.get_nodes()[1]
        assert len(collector.errors) == 1
        assert collector.errors[0] is result.get_errors()[0]

    def test_in_fail_fast_parse_the_stream_observer_sees_every_error(self) -> None:
        collector = CollectingStreamObserver()
        parser = Parser()
        parser.register_stream_observer(collector)

        with pytest.raises(ParseException):
            parser.parse("bad one\nbad two\n")
        assert len(collector.errors) == 2

    def test_an_observer_keeps_firing_in_parse_stream(self) -> None:
        from stxt import Observer

        created: list[str] = []

        class Creations(Observer):
            def on_create(self, node: Node, line_string: str) -> None:
                created.append(node.get_name())

        parser = Parser()
        parser.register_observer(Creations())
        parser.parse_stream(["Root: v", "\tChild: w"])

        assert created == ["Root", "Child"]
