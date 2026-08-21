"""Schema value types (STXT-SCHEMA-SPEC section 9): value form, content and children rules,
through SchemaValidator over a schema that declares one node per type."""

import pytest

from stxt import Parser, SchemaProviderMemory, SchemaValidator

TYPES = ["INLINE", "BLOCK", "TEXT", "MARKDOWN", "BOOLEAN", "URL", "INTEGER", "NATURAL", "NUMBER", "DATE",
         "TIME", "TIMESTAMP", "UUID", "EMAIL", "HEXADECIMAL", "BINARY", "BASE64", "GROUP", "ENUM"]

SCHEMA = "Schema (@stxt.schema): com.example.types\n" + "".join(
    f"\tNode: {t}\n\t\tType: {t}\n" + ("\t\tValues:\n\t\t\tValue: red\n\t\t\tValue: green\n" if t == "ENUM" else "")
    + ("\t\tChildren:\n\t\t\tChild: Any\n" if t in ("INLINE", "GROUP") else "")
    for t in TYPES
) + "\tNode: Any\n"

PROVIDER = SchemaProviderMemory()
PROVIDER.add_schema(SCHEMA)


def codes(text):
    node = Parser().parse(text)[0]
    return [e.code for e in SchemaValidator(PROVIDER, True).validate(node)]


def inline(type_, value):
    return f"{type_} (com.example.types): {value}\n"


def block(type_, *lines):
    return f"{type_} (com.example.types) >>\n" + "".join(f"\t{line}\n" for line in lines)


def test_all_18_types_are_registered():
    from stxt.schema import TypeRegistry
    assert sorted(TypeRegistry.names()) == sorted(TYPES)
    assert TypeRegistry.get("FOO") is None
    assert TypeRegistry.admits_children("INLINE") and TypeRegistry.admits_children("GROUP")
    assert not TypeRegistry.admits_children("TEXT")


# ---------------------------------------------------------------- forms

def test_inline_accepts_value_and_children_but_not_block():
    assert codes(inline("INLINE", "x")) == []
    assert codes(inline("INLINE", "") ) == []
    assert codes("INLINE (com.example.types): x\n\tAny: y\n") == []
    assert codes(block("INLINE", "x")) == ["NOT_ALLOWED_TEXT"]


def test_group_accepts_only_children():
    assert codes("GROUP (com.example.types):\n\tAny: y\n") == []
    assert codes(inline("GROUP", "value")) == ["INVALID_VALUE"]
    assert codes(block("GROUP", "x")) == ["INVALID_VALUE"]


def test_block_requires_the_block_form():
    assert codes(block("BLOCK", "x", "y")) == []
    assert codes(inline("BLOCK", "x")) == ["BLOCK_FORM_REQUIRED"]


@pytest.mark.parametrize("type_", ["TEXT", "MARKDOWN"])
def test_text_and_markdown_accept_both_forms_but_no_children(type_):
    assert codes(inline(type_, "any # text >>")) == []
    assert codes(block(type_, "line", "", "more")) == []
    assert codes(f"{type_} (com.example.types): x\n\tAny: y\n") == ["NOT_ALLOWED_CHILDREN_TEXT", "CHILD_NOT_DECLARED"]


def test_enum_is_case_sensitive_and_inline_only():
    assert codes(inline("ENUM", "red")) == []
    assert codes(inline("ENUM", "Red")) == ["INVALID_VALUE"]
    assert codes(inline("ENUM", "blue")) == ["INVALID_VALUE"]
    assert codes(block("ENUM", "red")) == ["NOT_ALLOWED_TEXT"]


# ---------------------------------------------------------------- regex types

@pytest.mark.parametrize("type_,good,bad", [
    ("BOOLEAN", ["true", "false"], ["True", "yes", "1", ""]),
    ("INTEGER", ["0", "-12", "+7"], ["1.5", "abc", "", "١٢"]),
    ("NATURAL", ["0", "42"], ["-1", "+1", "1.0"]),
    # STXT-SCHEMA-SPEC 9.4: the grammar of each type is normative; NUMBER is not the JSON number
    ("NUMBER", ["1", "-1.5", "+1", "1.", ".5", "007", "1e10", "1.2E-3", "+3."], ["abc", "1,5", "", "1e", "e5", "1.2.3"]),
    # calendar and clock ranges included
    ("DATE", ["2026-08-21", "2024-02-29", "0000-01-01", "9999-12-31"],
     ["2026-02-30", "2026-13-01", "2026-00-10", "2026-04-31", "2023-02-29", "2026-8-21", "21-08-2026", "2026-08-21T10:00"]),
    ("TIME", ["00:00:00", "23:59:59"], ["24:00:00", "10:60:00", "10:00:60", "10:30", "1:30:00", "10:30:00.5", "10:30:00Z"]),
    ("TIMESTAMP", ["2026-08-21T10:30", "2026-08-21T10:30:00", "2026-08-21T10:30:00.1", "2026-08-21T10:30:00.123456Z",
                   "2026-08-21T10:30:00+02:00", "2024-02-29T23:59:59-23:59"],
     ["2026-02-30T10:30", "2026-08-21T24:00", "2026-08-21T10:60:00", "2026-08-21T10:30:00+24:00", "2026-08-21T10:30:00+02:60",
      "2026-08-21 10:30:00", "2026-08-21", "2026-08-21T10:30:00.", "2026-08-21T10:30:00+0200"]),
    ("UUID", ["123e4567-e89b-12d3-a456-426614174000", "123E4567-E89B-12D3-A456-426614174000"], ["123e4567e89b12d3a456426614174000", "x"]),
    ("EMAIL",
     # STXT-SCHEMA-SPEC 9.4: bare address, or display name followed by the address between angle brackets
     ["ana@example.com", "a.b+c@sub.example.org", "Ana García <ana@example.com>", "Ana<ana@example.com>",
      "Ana García   <ana@example.com>", '"García, Ana" <ana@example.com>'],
     # the bracketed form needs a name, balanced brackets, a valid address and nothing after
     ["ana@", "@example.com", "ana@localhost", "a b@example.com", "<ana@example.com>", "   <ana@example.com>",
      "Ana <ana@>", "Ana <ana@localhost>", "Ana <ana@example.com", "Ana ana@example.com>", "Ana ana@example.com",
      "Ana <ana@example.com> extra", "Ana <ana@example.com> <ana@example.com>", "Ana <<ana@example.com>>"]),
])
def test_regex_types(type_, good, bad):
    for value in good:
        assert codes(inline(type_, value)) == [], f"{type_} should accept {value!r}"
    for value in bad:
        assert codes(inline(type_, value)) == ["INVALID_VALUE"], f"{type_} should reject {value!r}"
    assert codes(block(type_, good[0])) == ["NOT_ALLOWED_TEXT"]


# ---------------------------------------------------------------- specific types

def test_url_follows_the_grammar_of_the_spec():
    # STXT-SCHEMA-SPEC 9.4: absolute URL, scheme and host mandatory, own grammar (not urllib)
    good = ["https://stxt.dev", "https://stxt.dev/path/to?q=1&r=2#frag", "HTTP://EXAMPLE.COM/",
            "http://localhost:8080/", "ftp://user:pw@example.com/dir/", "http://[::1]:80/x",
            "http://192.168.0.1", "git+ssh://host/repo.git", "https://例え.jp/パス", "http://host?q=1"]
    bad = ["stxt.dev", "www.stxt.dev/x", "mailto:ana@example.com", "urn:isbn:9780131103627",
           "tel:+34600000000", "file:///etc/hosts", "http://", "://stxt.dev", "http:/stxt.dev",
           "1http://stxt.dev", "https://exa mple.com", "https://host:abc", "http://[::1", "http://user@",
           "https://host/path with space", ""]
    for value in good:
        assert codes(inline("URL", value)) == [], value
    for value in bad:
        assert codes(inline("URL", value)) == ["INVALID_VALUE"], value
    assert codes(block("URL", "https://stxt.dev")) == ["NOT_ALLOWED_TEXT"]


def test_binary_types_accept_inline_and_block_and_ignore_line_edges():
    assert codes(inline("HEXADECIMAL", "DEADbeef01")) == []
    assert codes(inline("HEXADECIMAL", "#FF")) == ["INVALID_VALUE"]
    assert codes(block("HEXADECIMAL", "  DEAD ", "", "beef")) == []
    assert codes(block("HEXADECIMAL", "DE AD")) == ["INVALID_VALUE"], "whitespace inside a line is kept"

    assert codes(inline("BINARY", "0101")) == []
    assert codes(inline("BINARY", "0102")) == ["INVALID_VALUE"]
    assert codes(block("BINARY", "01", "10")) == []


def test_base64():
    assert codes(inline("BASE64", "SGVsbG8=")) == []
    assert codes(inline("BASE64", "SGVsbG8")) == [], "missing padding is tolerated"
    assert codes(block("BASE64", "SGVs", "bG8=")) == []
    assert codes(inline("BASE64", "SGVsbG8*")) == ["INVALID_VALUE"]
    assert codes(inline("BASE64", "YR")) == ["INVALID_VALUE"], "leftover bits are rejected"
    assert codes(inline("BASE64", "SGVsbG8-")) == ["INVALID_VALUE"], "url-safe alphabet is rejected"


# ---------------------------------------------------------------- content model and cardinalities

CARD_SCHEMA = """Schema (@stxt.schema): com.example.card
	Node: Doc
		Children:
			Child: Title
				Min: 1
				Max: 1
			Child: Tag
				Max: 2
			Child: Ref (com.example.other)
	Node: Title
	Node: Tag
"""


def test_closed_content_model_and_cardinalities():
    provider = SchemaProviderMemory()
    provider.add_schema(CARD_SCHEMA)

    def card_codes(text):
        return [(e.code, e.line) for e in SchemaValidator(provider, True).validate(Parser().parse(text)[0])]

    assert card_codes("Doc (com.example.card):\n\tTitle: t\n\tTag: a\n\tTag: b\n") == []
    assert card_codes("Doc (com.example.card):\n") == [("INVALID_NUMBER", 1)]
    assert card_codes("Doc (com.example.card):\n\tTitle: t\n\tTag: a\n\tTag: b\n\tTag: c\n") == \
        [("INVALID_NUMBER", 1), ("INVALID_NUMBER", 3), ("INVALID_NUMBER", 4), ("INVALID_NUMBER", 5)]
    assert card_codes("Doc (com.example.card):\n\tTitle: t\n\tOther: x\n") == [("CHILD_NOT_DECLARED", 3), ("NODE_NOT_EXIST_IN_SCHEMA", 3)]
    assert card_codes("Unknown (com.example.card):\n") == [("NODE_NOT_EXIST_IN_SCHEMA", 1)]
    # A cross-namespace child is declared here and validated by its own schema (missing => finding)
    assert card_codes("Doc (com.example.card):\n\tTitle: t\n\tRef (com.example.other): x\n") == [("SCHEMA_NOT_FOUND", 3)]


@pytest.mark.parametrize("text,code", [
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: TEXT\n\t\tChildren:\n\t\t\tChild: A\n", "CHILDREN_NOT_ALLOWED_FOR_TYPE"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: TEXT\n\t\tValues:\n\t\t\tValue: v\n", "VALUES_ONLY_SUPPORTED_BY_ENUM"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: ENUM\n", "VALUES_EMPTY_FOR_ENUM"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: ENUM\n\t\tValues:\n\t\t\tValue: v\n\t\t\tValue: v\n", "VALUE_DUPLICATED"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tChildren:\n\t\t\tChild: B\n\t\t\t\tMin: 2\n\t\t\t\tMax: 1\n\tNode: B\n", "MIN_GREATER_THAN_MAX"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tChildren:\n\t\t\tChild: Missing\n", "CHILD_NOT_DEFINED"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\tNode: a\n", "NODE_DEF_ALREADY_DEFINED"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tChildren:\n\t\t\tChild: B\n\t\t\tChild: b\n\tNode: B\n", "CHILD_DEF_ALREADY_DEFINED"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: FOO\n", "INVALID_VALUE"),
    ("Schema (@stxt.schema): nodots\n\tNode: A\n", "INVALID_NAMESPACE"),
    ("Doc (@stxt.schema): com.example.x\n", "NODE_NOT_EXIST_IN_SCHEMA"),
    ("Schema (com.example.x): com.example.x\n\tNode: A\n", "SCHEMA_NOT_FOUND"),
])
def test_schema_errors(text, code):
    with pytest.raises(Exception) as info:
        SchemaProviderMemory().add_schema(text)
    assert getattr(info.value, "code", None) == code, repr(info.value)
