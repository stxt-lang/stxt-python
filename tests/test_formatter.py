"""The reformatting of STXT-TREE-SPEC 12; a replica of the TypeScript suite."""

from stxt import Formatter, IndentStyle, Parser, to_canonical_json

TABS, SPACES_4 = IndentStyle.TABS, IndentStyle.SPACES_4


def fmt(text, style=TABS):
    return Formatter.format(text, style).text


def canonical(text):
    return to_canonical_json(Parser().parse(text))


MESSY = "\n".join(["# top comment", "Documento (test.fmt):   ", "    # indented comment", "    Titulo:Hello   ", "",
                   "\tCuerpo >>", "\t\tfirst line", "", "\t\t    indented content", "\t\t\t\t", "\tAfter (test.fmt): block", ""])
MESSY_TABS = "\n".join(["# top comment", "Documento (test.fmt):", "\t# indented comment", "\tTitulo: Hello", "",
                        "\tCuerpo >>", "\t\tfirst line", "\t\t", "\t\t    indented content", "", "\tAfter (test.fmt): block", ""])
MESSY_SPACES = "\n".join(["# top comment", "Documento (test.fmt):", "    # indented comment", "    Titulo: Hello", "",
                          "    Cuerpo >>", "        first line", "        ", "            indented content", "",
                          "    After (test.fmt): block", ""])


def test_rewrites_the_indentation_according_to_the_level_of_the_node():
    assert fmt("Padre: p\n    Hijo: v") == "Padre: p\n\tHijo: v"
    assert fmt("Padre: p\n\tHijo: v", SPACES_4) == "Padre: p\n    Hijo: v"


def test_writes_exactly_one_space_after_the_colon_and_none_without_a_value():
    assert fmt("Doc:    hola   ") == "Doc: hola"
    assert fmt("Doc:hola") == "Doc: hola"
    assert fmt("Contenedor:") == "Contenedor:"
    assert fmt("Contenedor:   ") == "Contenedor:"
    assert fmt("Contenedor (ns.uno):") == "Contenedor (ns.uno):"


def test_writes_the_namespace_only_where_the_source_wrote_it():
    text = "Doc (a.b): x\n\tHijo (a.b): y\n\tOtro: z\n\tBloque (c.d) >>\n\t\ttexto"
    assert fmt(text) == text
    assert fmt("Doc (A.B):x\n\tHijo   (a.b):y") == "Doc (a.b): x\n\tHijo (a.b): y"


def test_renders_a_block_line_as_name_one_space_and_arrows():
    assert fmt("Doc  >>\n\tuna") == "Doc >>\n\tuna"
    assert fmt("Doc>>   \n\tuna") == "Doc >>\n\tuna"


def test_keeps_the_name_as_parsed_blanks_collapsed():
    assert fmt("Mi   Nodo  : v") == "Mi Nodo: v"


def test_reindents_block_lines_keeping_their_own_extra_indentation():
    assert fmt("Doc >>\n    una línea\n        sangrada") == "Doc >>\n\tuna línea\n\t    sangrada"
    assert fmt("Doc >>\n\tuna línea\n\t\tsangrada", SPACES_4) == "Doc >>\n    una línea\n    \tsangrada"


def test_indents_the_blank_lines_of_a_block_before_more_text_final_ones_stay_plain():
    # STXT-SPEC 10.3: a blank line before more block text gets the block's indentation;
    # the final blank lines of a block are not content and stay plain.
    assert fmt("Doc >>\n\tuna\n\n\t\t\t\n\totra") == "Doc >>\n\tuna\n\t\n\t\n\totra"
    assert fmt("Doc >>\n\tuna\n\n\totra", SPACES_4) == "Doc >>\n    una\n    \n    otra"
    assert fmt("Doc >>\n\tuna\n\t\t\t") == "Doc >>\n\tuna\n"
    assert fmt("Doc >>\n\tuna\n\t\t\t\nOtro: x") == "Doc >>\n\tuna\n\nOtro: x"
    assert fmt("Padre:\n\tHijo: v\n\t\n\tOtro: w") == "Padre:\n\tHijo: v\n\n\tOtro: w"


def test_keeps_the_text_of_the_block_byte_identical():
    text = "Doc >>\n\tuna\n\n\t\t  dos\n\t\t\t"
    block = lambda t: Parser().parse(t)[0].get_text()
    assert block(text) == "una\n\n\t  dos"
    assert block(fmt(text)) == block(text)
    assert block(fmt(text, SPACES_4)) == block(text)


def test_removes_the_trailing_blanks_of_a_text_line():
    assert fmt("Doc >>\n\tuna   \n\tdos\t") == "Doc >>\n\tuna\n\tdos"


COMMENTS = "\n".join(["# top comment", "Documento (test.fmt):", "\t# tab comment", "    # spaces comment", "\tTitulo: Hello",
                      "\t\t# two units, after a childless node   ", ""])


def test_converts_the_indentation_units_of_every_comment():
    assert fmt(COMMENTS) == "\n".join(["# top comment", "Documento (test.fmt):", "\t# tab comment", "\t# spaces comment",
                                       "\tTitulo: Hello", "\t\t# two units, after a childless node", ""])
    assert fmt(COMMENTS, SPACES_4) == "\n".join(["# top comment", "Documento (test.fmt):", "    # tab comment",
                                                 "    # spaces comment", "    Titulo: Hello",
                                                 "        # two units, after a childless node", ""])
    assert fmt("#  a   b\t c") == "#  a   b\t c"


def test_keeps_everything_around_the_node_lines():
    assert fmt(MESSY) == MESSY_TABS
    assert fmt(MESSY, SPACES_4) == MESSY_SPACES


def test_is_idempotent_and_round_trips_between_the_two_styles():
    assert fmt(MESSY_TABS) == MESSY_TABS
    assert fmt(MESSY_SPACES, SPACES_4) == MESSY_SPACES
    assert fmt(MESSY_SPACES) == MESSY_TABS
    assert fmt(MESSY_TABS, SPACES_4) == MESSY_SPACES


def test_keeps_the_line_ending_the_final_newline_and_removes_a_bom():
    assert fmt("Doc:\r\n    Hijo: v\r\n") == "Doc:\r\n\tHijo: v\r\n"
    assert fmt("Doc:\n    Hijo: v") == "Doc:\n\tHijo: v"
    assert fmt("Doc:\n    Hijo: v\n") == "Doc:\n\tHijo: v\n"
    assert fmt("") == ""
    assert fmt("﻿Doc: x\n") == "Doc: x\n"
    assert fmt("﻿# comment\nDoc: x\n") == "# comment\nDoc: x\n"


def test_produces_the_same_canonical_tree_and_no_errors():
    assert canonical(fmt(MESSY)) == canonical(MESSY)
    assert canonical(fmt(MESSY, SPACES_4)) == canonical(MESSY)
    assert Formatter.format(MESSY).errors == []


def test_reports_the_errors_and_converts_only_the_units_of_the_lines_the_tree_does_not_describe():
    result = Formatter.format("Doc: x\n\t  Mixed: y\n\t\t\tJump: z\n", SPACES_4)
    assert [f"{e.line}:{e.code}" for e in result.errors] == ["2:INDENTATION_MIXED", "3:INDENTATION_LEVEL_NOT_VALID"]
    assert result.text == "Doc: x\n      Mixed: y\n            Jump: z\n"

    text = "Padre: p\n\t\t\tHijo: v"
    assert fmt(text) == text

    still = Formatter.format("Doc:   x\n    Hijo:y\n\t\t\t\tJump: z")
    assert len(still.errors) == 1
    assert still.text == "Doc: x\n\tHijo: y\n\t\t\t\tJump: z"


class TestFormatterParserLimits:
    """The optional limit kwargs of Formatter.format (STXT-SPEC 11.2)."""

    def test_default_limits_apply(self) -> None:
        result = Formatter.format("Name: " + "x" * 10000 + "\n")

        assert [e.code for e in result.errors] == ["LIMIT_LINE_LENGTH_EXCEEDED"]

    def test_minus_one_disables_a_limit(self) -> None:
        text = "Name: " + "x" * 10000 + "\n"
        result = Formatter.format(text, IndentStyle.TABS, max_line_length=-1)

        assert result.errors == []
        assert result.text == text

    def test_after_an_abort_undescribed_lines_are_unit_converted_only(self) -> None:
        text = "A: 1\n    B: " + "y" * 30 + "\n    C: 3\n"
        result = Formatter.format(text, IndentStyle.TABS, max_line_length=20)

        assert [e.code for e in result.errors] == ["LIMIT_LINE_LENGTH_EXCEEDED"]
        assert result.text == "A: 1\n\tB: " + "y" * 30 + "\n\tC: 3\n"
