"""Core conformance regressions of the parser: STXT-SPEC error codes and behaviours."""

import pytest

import stxt
from stxt import (InlineNode, LineIndent, Observer, ParseException, Parser, RuntimeException, SPEC_VERSION,
                  TextNode, ValidationException, parse_line)


def _codes(text):
    return [e.code for e in Parser().parse_result(text).get_errors()]


def _first(text):
    return Parser().parse(text)[0]


# ---------------------------------------------------------------- names (4)

def test_accepts_a_decomposed_unicode_name_and_gives_it_the_nfc_canonical_name():
    node = _first("Café: value\n")
    assert node.get_name() == "Café"
    assert node.get_canonical_name() == "café"
    assert node.get_canonical_name() == _first("Café: value\n").get_canonical_name()


def test_canonical_name_keeps_accents_and_is_insensitive_to_case_and_separators():
    assert _first("Año  Nuevo: x\n").get_canonical_name() == "año-nuevo"
    assert _first("AÑO_NUEVO: x\n").get_canonical_name() == "año-nuevo"
    assert _first("Ano Nuevo: x\n").get_canonical_name() != "año-nuevo"
    assert _first("My   Name  : x\n").get_name() == "My Name"


@pytest.mark.parametrize("line", ["Invalid!: x", "___: x", "Name@: x", ": value"])
def test_invalid_names_are_rejected(line):
    codes = _codes(line + "\n")
    assert codes and codes[0] in ("INVALID_NODE_NAME", "INVALID_LINE"), codes


def test_accepts_combining_marks_in_names_and_still_requires_a_letter_or_digit():
    # STXT-SPEC 4.2: Mn and Mc are name characters; Me is not; a name of only marks is not a name
    hindi, q = Parser().parse("\u0939\u093f\u0902\u0926\u0940: x\nQ\u0301: y\n")
    assert hindi.get_canonical_name() == "\u0939\u093f\u0902\u0926\u0940"
    assert q.get_canonical_name() == "q\u0301"
    assert _codes("\u0301: only a mark\n") == ["INVALID_NODE_NAME"]
    assert _codes("a\u20dd: enclosing mark\n") == ["INVALID_NODE_NAME"]


# ---------------------------------------------------------------- lines (5, 6, 11)

def test_a_line_without_separator_is_invalid():
    assert _codes("Just text\n") == ["INVALID_LINE"]


def test_a_block_node_cannot_carry_inline_content():
    assert _codes("Body >> text\n") == ["BLOCK_VALUE_NOT_ALLOWED"]


def test_the_first_separator_decides_the_form():
    node = _first("Name: value >> more\n")
    assert isinstance(node, InlineNode)
    assert node.get_value() == "value >> more"
    assert _codes("Name >> : x\n") == ["INVALID_LINE"], "'>>' before ':' is not an inline node"


def test_values_are_trimmed_and_block_lines_right_trimmed():
    assert _first("Name:    spaced value   \n").get_value() == "spaced value"
    text = _first("T >>\n\t  keeps left   \n\tline\n")
    assert isinstance(text, TextNode)
    assert list(text.get_text_lines()) == ["  keeps left", "line"]


# ---------------------------------------------------------------- namespaces (7)

def test_namespaces_are_lower_cased_inherited_and_validated():
    doc = _first("Doc (Com.Example.Docs): x\n\tChild: y\n")
    assert doc.get_declared_namespace() == "com.example.docs"
    assert doc.get_children()[0].get_namespace() == "com.example.docs"
    assert doc.get_children()[0].get_declared_namespace() == ""


@pytest.mark.parametrize("line", [
    "Doc (nodots): x", "Doc (): x", "Doc (com.example: x", "Doc com.example): x",
    "Doc ( com.example ): x", "Doc (com.Ex_ample.docs): x", "Doc (@stxt): x",
])
def test_invalid_namespaces(line):
    assert _codes(line + "\n") == ["INVALID_NAMESPACE"]


def test_namespaces_are_not_inherited_laterally_between_roots():
    docs = Parser().parse("A (com.a.ns): x\nB: y\n")
    assert docs[1].get_namespace() == ""


def test_reserved_namespaces_are_accepted():
    assert _first("Schema (@stxt.schema): com.x.y\n").get_namespace() == "@stxt.schema"


# ---------------------------------------------------------------- indentation (8)

def test_tabs_and_four_spaces_are_both_one_level():
    docs = Parser().parse("A: x\n\tB: y\n    C: z\n")
    assert [c.get_name() for c in docs[0].get_children()] == ["B", "C"]


def test_mixed_indentation_in_a_line_is_an_error():
    assert _codes("A: x\n\t B: y\n") == ["INDENTATION_MIXED"]
    assert _codes("A: x\n \tB: y\n") == ["INDENTATION_MIXED"]


def test_spaces_not_multiple_of_four_are_an_error():
    assert _codes("A: x\n  B: y\n") == ["INDENTATION_SPACES_NOT_VALID"]


def test_jumping_more_than_one_level_is_an_error():
    assert _codes("A: x\n\t\tB: y\n") == ["INDENTATION_LEVEL_NOT_VALID"]


def test_indentation_of_empty_lines_is_not_validated():
    docs = Parser().parse("A: x\n   \n\t\t  \n\tB: y\n")
    assert [c.get_name() for c in docs[0].get_children()] == ["B"]


# ---------------------------------------------------------------- multiple roots, encoding (3, 8.5)

def test_multiple_roots_and_bom_and_crlf():
    docs = Parser().parse("\ufeffA: 1\r\n\tB: 2\r\nC: 3\r\n")
    assert [d.get_name() for d in docs] == ["A", "C"]
    assert docs[0].get_children()[0].get_value() == "2"


def test_empty_content_gives_no_documents():
    assert Parser().parse("") == []
    assert Parser().parse("\n\n# only comments\n") == []


# ---------------------------------------------------------------- text blocks (10)

def test_block_lines_are_literal_and_keep_inner_blank_lines_but_not_the_final_break():
    text = _first("T >>\n\tline: with # marks >>\n\n\t\tindented\n\t\n\tlast\n")
    assert list(text.get_text_lines()) == ["line: with # marks >>", "", "\tindented", "", "last"]


def test_block_lines_use_relative_indentation():
    # One level beyond the block node marks the content; the rest of the indentation is literal
    text = _first("T >>\n        two levels\n            three\n")
    assert list(text.get_text_lines()) == ["    two levels", "        three"]
    text = _first("A:\n\tT >>\n\t\t\tdeep\n\t\tflat\n").get_children()[0]
    assert list(text.get_text_lines()) == ["\tdeep", "flat"]


def test_a_block_ends_at_a_line_of_its_own_level():
    docs = Parser().parse("A: x\n\tT >>\n\t\tinside\n\tNext: y\n")
    a = docs[0]
    assert [c.get_name() for c in a.get_children()] == ["T", "Next"]
    assert list(a.get_children()[0].get_text_lines()) == ["inside"]


def test_mixed_indentation_inside_a_block_line_is_an_error_but_not_for_empty_lines():
    # The prefix covering the block level must be homogeneous; what follows is content
    assert _codes("A:\n\tT >>\n\t    x\n") == ["INDENTATION_MIXED"]
    assert _codes("A:\n\tT >>\n \tx\n") == ["INDENTATION_MIXED"]
    assert list(_first("T >>\n\t inside\n").get_text_lines()) == [" inside"]
    text = _first("A:\n\tT >>\n\t    \n\t\tok\n").get_children()[0]
    assert list(text.get_text_lines()) == ["", "ok"]


def test_a_block_node_at_eof_has_no_spurious_last_line():
    assert list(_first("T >>\n\tone\n").get_text_lines()) == ["one"]
    assert list(_first("T >>\n\tone").get_text_lines()) == ["one"]
    assert list(_first("T >>\n").get_text_lines()) == []


def test_a_comment_at_the_level_of_the_block_node_closes_the_block():
    # STXT-SPEC 6.1 / 9.1: a block is a literal, it cannot be commented from inside
    root = _first("Root:\n\tBody >>\n\t\tfirst\n\t\t# still text\n\t# closes the block\n\tAfter: sibling\n")
    body, after = root.get_children()
    assert isinstance(body, TextNode)
    assert list(body.get_text_lines()) == ["first", "# still text"]
    assert after.get_name() == "After" and after.get_value() == "sibling"


def test_a_shallower_comment_also_closes_the_block_and_nothing_else():
    root = _first("Root:\n\tBody >>\n\t\tline\n# root-level comment\n\tAfter: x\n")
    assert [c.get_name() for c in root.get_children()] == ["Body", "After"]
    assert list(root.get_children()[0].get_text_lines()) == ["line"]


def test_text_after_a_closing_comment_is_a_parse_error():
    # The de-indented '#' line no longer vanishes silently: the next text line fails
    assert _codes("Root:\n\tBody >>\n\t\tfirst\n\t# oops\n\t\tsecond\n") == ["INDENTATION_LEVEL_NOT_VALID"]
    assert _codes("Body >>\n\tfirst\n# oops\n\tsecond\n") == ["INVALID_LINE"]


def test_a_comment_after_the_last_line_of_a_block_is_still_just_a_comment():
    root = _first("Root:\n\tBody >>\n\t\tonly\n\t# trailing comment\n")
    assert list(root.get_children()[0].get_text_lines()) == ["only"]


# ---------------------------------------------------------------- comment indentation (9, 11)

def _first_error(text):
    return Parser().parse_result(text).get_errors()[0]


def test_a_comment_mixing_tabs_and_spaces_is_mixed_indentation():
    error = _first_error("A: x\n\t  # mixed\n\tB: y\n")
    assert (error.code, error.line) == ("INDENTATION_MIXED", 2)


def test_a_comment_with_spaces_not_multiple_of_four_is_invalid_number_spaces():
    error = _first_error("A: x\n  # two spaces\n\tB: y\n")
    assert (error.code, error.line) == ("INDENTATION_SPACES_NOT_VALID", 2)


def test_a_comment_jumping_more_than_one_level_is_indentation_level_not_valid():
    error = _first_error("A: x\n\t\t# too deep\n\tB: y\n")
    assert (error.code, error.line) == ("INDENTATION_LEVEL_NOT_VALID", 2)


def test_comments_at_every_reachable_level_are_valid_and_produce_no_node():
    # Level 0, level 1 and last+1 after a childless node
    root = _first("# level 0\nRoot:\n\t# level 1\n\tFirst: 1\n\t\t# last + 1, First has no children\n\tSecond: 2\n")
    assert [c.get_name() for c in root.get_children()] == ["First", "Second"]
    assert all(isinstance(c, InlineNode) for c in root.get_children())


def test_a_node_after_a_level_two_comment_is_checked_against_the_last_node_not_the_comment():
    # The comment never becomes the reference level: Second is a child of Root
    root = _first("Root:\n\tFirst: 1\n\t\t# deeper comment\n\tSecond: 2\n")
    assert [c.get_name() for c in root.get_children()] == ["First", "Second"]
    # ...and a level-3 node after that comment is still a jump from First (level 1)
    error = _first_error("Root:\n\tFirst: 1\n\t\t# deeper comment\n\t\t\tThird: 3\n")
    assert (error.code, error.line) == ("INDENTATION_LEVEL_NOT_VALID", 4)


# ---------------------------------------------------------------- multi-error mode

def test_parse_result_collects_every_error_and_keeps_going():
    result = Parser().parse_result("A: x\n\t\tB: y\nnot a line\nC (bad): z\nD: ok\n")
    assert [e.code for e in result.get_errors()] == ["INDENTATION_LEVEL_NOT_VALID", "INVALID_LINE", "INVALID_NAMESPACE"]
    assert [e.line for e in result.get_errors()] == [2, 3, 4]
    assert [d.get_name() for d in result.get_nodes()] == ["A", "D"]


def test_parse_raises_the_first_error():
    with pytest.raises(ParseException) as info:
        Parser().parse("A: x\n\t\tB: y\nnot a line\n")
    assert info.value.code == "INDENTATION_LEVEL_NOT_VALID"
    assert info.value.line == 2


# ---------------------------------------------------------------- exception contract

def test_message_is_only_the_description_and_the_frame_lives_in_str():
    """Message framing (0.10.0, the same in every port): ``message`` carries no code and no
    line; ``__str__`` is ``[CODE] line N: message`` / ``[CODE] message``."""
    with pytest.raises(ParseException) as info:
        Parser().parse("A: x\n\t\tB: y\n")
    error = info.value
    assert error.message == "Level of indent incorrect: 2"
    assert error.get_message() == error.message
    assert error.code == "INDENTATION_LEVEL_NOT_VALID" and error.line == 2
    assert str(error) == "[INDENTATION_LEVEL_NOT_VALID] line 2: Level of indent incorrect: 2"
    assert error.args == ("Level of indent incorrect: 2",)

    moved = error.with_line(9)
    assert type(moved) is ParseException
    assert (moved.line, moved.code, moved.message) == (9, error.code, error.message)
    assert str(moved) == "[INDENTATION_LEVEL_NOT_VALID] line 9: Level of indent incorrect: 2"

    validation = ValidationException(3, "INVALID_VALUE", "Bad value")
    assert validation.message == "Bad value"
    assert str(validation) == "[INVALID_VALUE] line 3: Bad value"
    assert str(validation.with_line(4)) == "[INVALID_VALUE] line 4: Bad value"
    assert type(validation.with_line(4)) is ValidationException

    runtime = RuntimeException("AMBIGUOUS_CHILD", "Ambiguous")
    assert runtime.message == "Ambiguous" and runtime.get_message() == "Ambiguous"
    assert str(runtime) == "[AMBIGUOUS_CHILD] Ambiguous"


def test_no_error_message_carries_its_own_code_or_line():
    """The description never repeats the frame, whichever module raises it."""
    documents = [
        "A: x\n\t\tB: y\n",
        "A: x\n   B: y\n",
        "A: x\n\t  B: y\n",
        "not a line\n",
        "A >> x\n",
        "A (bad): x\n",
        "-: x\n",
    ]
    for text in documents:
        for error in Parser().parse_result(text).get_errors():
            assert f"[{error.code}]" not in error.message, text
            assert not error.message.lower().startswith("error at line"), text
            assert f"line {error.line}" not in error.message.lower() or "indent" in error.message.lower(), text


def test_spec_version_is_the_version_of_the_specifications():
    assert SPEC_VERSION == "1.0"
    assert stxt.SPEC_VERSION is SPEC_VERSION
    assert "SPEC_VERSION" in stxt.__all__ and "__version__" in stxt.__all__
    assert stxt.__version__ != SPEC_VERSION, "the package version is not the spec version"


# ---------------------------------------------------------------- observers

class Recorder(Observer):
    def __init__(self):
        self.events = []

    def on_create(self, node, line_string):
        self.events.append(("create", node.get_name(), node.get_level(), node.get_namespace()))

    def on_finish(self, node):
        self.events.append(("finish", node.get_name()))

    def on_comment(self, line_number, line_string):
        self.events.append(("comment", line_number))

    def on_text_line(self, node, line_number, line_string, line_indent):
        self.events.append(("text", node.get_name(), line_indent.line_without_indent))


def test_observers_see_the_streaming_events_with_the_parent_already_attached():
    recorder = Recorder()
    parser = Parser()
    parser.register_observer(recorder)
    parser.parse("# c\nA (com.a.ns): x\n\tT >>\n\t\tline\n\t# closes T\n\tB: y\n")
    assert recorder.events == [
        ("comment", 1),
        ("create", "A", 0, "com.a.ns"),
        ("create", "T", 1, "com.a.ns"),
        ("text", "T", "line"),
        ("finish", "T"),
        ("comment", 5),
        ("create", "B", 1, "com.a.ns"),
        ("finish", "B"),
        ("finish", "A"),
    ]


# ---------------------------------------------------------------- parse_line

def test_parse_line_splits_indentation_and_content():
    li = parse_line("\t\tName: value", False, 1, 1)
    assert isinstance(li, LineIndent)
    assert (li.indent_level, li.line_without_indent, li.is_comment, li.is_block, li.indent_length) == (2, "Name: value", False, False, 2)
    comment = parse_line("\t# hi", False, 0, 1)
    assert comment.is_comment and comment.line_without_indent == " hi"


# ---------------------------------------------------------------- blanks (4)

def test_blanks_are_only_space_and_tab_so_an_nbsp_is_content():
    root = _first("Root:\n\tTrailing: Joan \n\tLeading: Joan\n\tOnly: \n\tBlock >>\n\t\tfirst \n\t\t \n\t\tin the middle\n")
    trailing, leading, only, block = root.get_children()
    assert trailing.get_value() == "Joan "
    assert leading.get_value() == " Joan"
    assert only.get_value() == " "
    assert list(block.get_text_lines()) == ["first ", " ", "in the middle"]


def test_a_line_holding_only_an_nbsp_is_not_empty():
    assert _codes(" \n") == ["INVALID_LINE"]
    assert _codes("Block >> \n") == ["BLOCK_VALUE_NOT_ALLOWED"]
    assert _codes("Root: x\n \t\n\n") == []


def test_an_nbsp_is_not_trimmed_from_a_name_which_makes_it_invalid():
    assert _codes("Name : x\n") == ["INVALID_NODE_NAME"]
    assert _codes("A B: x\n") == ["INVALID_NODE_NAME"]
    assert _first("Name \t: x\n").get_name() == "Name"
