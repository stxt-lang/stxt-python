"""Schema value types (STXT-SCHEMA-SPEC section 9): value form, content and children rules,
through SchemaValidator over a schema that declares one node per type."""

import pytest

from stxt import Parser, SchemaProviderMemory, SchemaValidator, ValidationException, transform_node_to_schema

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
    assert codes(block("INLINE", "x")) == ["BLOCK_FORM_NOT_ALLOWED"]


def test_group_accepts_only_children():
    assert codes("GROUP (com.example.types):\n\tAny: y\n") == []
    assert codes(inline("GROUP", "value")) == ["VALUE_NOT_ALLOWED"]
    assert codes(block("GROUP", "x")) == ["VALUE_NOT_ALLOWED"]


def test_block_requires_the_block_form():
    assert codes(block("BLOCK", "x", "y")) == []
    assert codes(inline("BLOCK", "x")) == ["BLOCK_FORM_REQUIRED"]


@pytest.mark.parametrize("type_", ["TEXT", "MARKDOWN"])
def test_text_and_markdown_accept_both_forms_but_no_children(type_):
    assert codes(inline(type_, "any # text >>")) == []
    assert codes(block(type_, "line", "", "more")) == []
    assert codes(f"{type_} (com.example.types): x\n\tAny: y\n") == ["CHILDREN_NOT_ALLOWED", "CHILD_NOT_DECLARED"]


def test_enum_is_case_sensitive_and_inline_only():
    assert codes(inline("ENUM", "red")) == []
    assert codes(inline("ENUM", "Red")) == ["INVALID_VALUE"]
    assert codes(inline("ENUM", "blue")) == ["INVALID_VALUE"]
    assert codes(block("ENUM", "red")) == ["BLOCK_FORM_NOT_ALLOWED"]


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
     # STXT-SCHEMA-SPEC 9.4: bare address, or display name followed by the address between angle
     # brackets; permissive dots (no RFC 5322 dot-atom) and the RFC 5321 practical length limits
     ["ana@example.com", "a.b+c@sub.example.org", "a..b@example.com", ".ana@example.com",
      "a!#$%&'*+/=?^_`{|}~-@x.co", "a" * 64 + "@example.com", "ana@example." + "a" * 63,
      "Ana García <ana@example.com>", "Ana<ana@example.com>",
      "Ana García   <ana@example.com>", '"García, Ana" <ana@example.com>'],
     # the bracketed form needs a name, balanced brackets, a valid address and nothing after;
     # ASCII only (no EAI), no digits in the TLD, and one over each length limit fails
     ["ana@", "@example.com", "ana@localhost", "a b@example.com", "josé@example.com", "ana@example.c0m",
      "a" * 65 + "@example.com", "ana@example." + "a" * 64,
      "<ana@example.com>", "   <ana@example.com>",
      "Ana <ana@>", "Ana <ana@localhost>", "Ana <ana@example.com", "Ana ana@example.com>", "Ana ana@example.com",
      "Ana <ana@example.com> extra", "Ana <ana@example.com> <ana@example.com>", "Ana <<ana@example.com>>",
      "Ana < ana@example.com >"]),
])
def test_regex_types(type_, good, bad):
    for value in good:
        assert codes(inline(type_, value)) == [], f"{type_} should accept {value!r}"
    for value in bad:
        assert codes(inline(type_, value)) == ["INVALID_VALUE"], f"{type_} should reject {value!r}"
    assert codes(block(type_, good[0])) == ["BLOCK_FORM_NOT_ALLOWED"]


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
    assert codes(block("URL", "https://stxt.dev")) == ["BLOCK_FORM_NOT_ALLOWED"]


def test_binary_types_accept_inline_and_block_and_ignore_line_edges():
    assert codes(inline("HEXADECIMAL", "DEADbeef01")) == []
    assert codes(inline("HEXADECIMAL", "#FF")) == ["INVALID_VALUE"]
    assert codes(block("HEXADECIMAL", "  DEAD ", "", "beef")) == []
    assert codes(block("HEXADECIMAL", "DE AD")) == [], "blanks inside a line are removed too (9.5)"

    assert codes(inline("BINARY", "0101")) == []
    assert codes(inline("BINARY", "0102")) == ["INVALID_VALUE"]
    assert codes(block("BINARY", "01", "10")) == []


def test_binary_types_drop_every_blank_before_validating():
    """STXT-SCHEMA-SPEC 9.5 (since 2026-08-21): spaces and tabs are removed wherever they are,
    in both forms; nothing else is."""
    assert codes(inline("HEXADECIMAL", "DE AD BE EF")) == []
    assert codes(inline("HEXADECIMAL", "DE\tAD")) == []
    assert codes(inline("BINARY", "1010 1010")) == []
    assert codes(inline("BASE64", "SG Vs bG 8=")) == []
    wrapped = "U1RYVCBpcyBhIGh1bWFuLWZpcnN0IHRleHQgZm9ybWF0IHRoYXQgaXMgZWFzeSB0byByZWFkIGFuZCB0cml2aWFs" \
              "IHRvIHBhcnNlLCBkZXNpZ25lZCB3aXRoIHNlY3VyaXR5IGluIG1pbmQu"
    lines = [wrapped[i:i + 76] for i in range(0, len(wrapped), 76)]
    assert len(lines) > 1 and len(lines[0]) == 76
    assert codes(block("BASE64", *[f"  {line}\t " for line in lines])) == []
    assert codes(block("BASE64", "SG Vs", "\tbG 8=")) == []
    # Only blanks are removed
    assert codes(inline("HEXADECIMAL", "DE:AD")) == ["INVALID_VALUE"]
    assert codes(inline("HEXADECIMAL", "DE-AD")) == ["INVALID_VALUE"]
    assert codes(inline("BASE64", "SG:Vs")) == ["INVALID_VALUE"]
    assert codes(inline("BINARY", "10\u00a010")) == ["INVALID_VALUE"], "an NBSP is not a blank"
    # Empty after removing the blanks
    assert codes(inline("HEXADECIMAL", "")) == ["INVALID_VALUE"]
    assert codes(inline("HEXADECIMAL", " \t ")) == ["INVALID_VALUE"]
    assert codes(block("BINARY", "  ", "\t")) == ["INVALID_VALUE"]
    assert codes(block("BASE64", " ")) == ["INVALID_VALUE"]


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
    assert card_codes("Doc (com.example.card):\n") == [("TOO_FEW_CHILDREN", 1)]
    assert card_codes("Doc (com.example.card):\n\tTitle: t\n\tTag: a\n\tTag: b\n\tTag: c\n") == \
        [("TOO_MANY_CHILDREN", 1), ("TOO_MANY_CHILDREN", 3), ("TOO_MANY_CHILDREN", 4), ("TOO_MANY_CHILDREN", 5)]
    assert card_codes("Doc (com.example.card):\n\tTitle: t\n\tOther: x\n") == [("CHILD_NOT_DECLARED", 3), ("NODE_NOT_DEFINED_IN_SCHEMA", 3)]
    assert card_codes("Unknown (com.example.card):\n") == [("NODE_NOT_DEFINED_IN_SCHEMA", 1)]
    # A cross-namespace child is declared here and validated by its own schema (missing => finding)
    assert card_codes("Doc (com.example.card):\n\tTitle: t\n\tRef (com.example.other): x\n") == [("SCHEMA_NOT_FOUND", 3)]


@pytest.mark.parametrize("text,code", [
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: TEXT\n\t\tChildren:\n\t\t\tChild: A\n", "CHILDREN_NOT_ALLOWED_FOR_TYPE"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: TEXT\n\t\tValues:\n\t\t\tValue: v\n", "VALUES_NOT_ALLOWED_FOR_TYPE"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: ENUM\n", "VALUES_REQUIRED"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: ENUM\n\t\tValues:\n\t\t\tValue: v\n\t\t\tValue: v\n", "VALUE_DUPLICATED"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: ENUM\n\t\tValues:\n\t\t\tValue: x\n\t\t\tValue:\n", "VALUE_EMPTY"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: ENUM\n\t\tValues:\n\t\t\tValue: \t \n", "VALUE_EMPTY"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tChildren:\n\t\t\tChild: B\n\t\t\t\tMin: 2\n\t\t\t\tMax: 1\n\tNode: B\n", "MIN_GREATER_THAN_MAX"),
    # cardinalities are bounded to 2^32 - 1 (SCHEMA-SPEC 10)
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tChildren:\n\t\t\tChild: B\n\t\t\t\tMax: 4294967296\n\tNode: B\n", "CARDINALITY_NOT_VALID"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tChildren:\n\t\t\tChild: Missing\n", "CHILD_NOT_DEFINED"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\tNode: a\n", "NODE_DUPLICATED"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tChildren:\n\t\t\tChild: B\n\t\t\tChild: b\n\tNode: B\n", "CHILD_DUPLICATED"),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: FOO\n", "INVALID_VALUE"),
    ("Schema (@stxt.schema): nodots\n\tNode: A\n", "SCHEMA_ROOT_NOT_VALID"),
    ("Schema (@stxt.schema):\n\tNode: A\n", "SCHEMA_NAMESPACE_EMPTY"),
    ("Doc (@stxt.schema): com.example.x\n", "NODE_NOT_DEFINED_IN_SCHEMA"),
    ("Schema (com.example.x): com.example.x\n\tNode: A\n", "SCHEMA_NOT_FOUND"),
])
def test_schema_errors(text, code):
    with pytest.raises(Exception) as info:
        SchemaProviderMemory().add_schema(text)
    assert getattr(info.value, "code", None) == code, repr(info.value)


def test_schema_cardinality_bound_itself_is_legal():
    # SCHEMA-SPEC 10: 4294967295 = 2^32 - 1 is the last legal Min/Max value
    SchemaProviderMemory().add_schema(
        "Schema (@stxt.schema): com.example.bound\n\tNode: A\n\t\tChildren:\n\t\t\tChild: B\n\t\t\t\tMax: 4294967295\n\tNode: B\n")


GROUP_SCHEMA = """Schema (@stxt.schema): com.example.group
	Node: Doc
		Children:
			Child: Meta
	Node: Meta
		Type: GROUP
"""


def test_a_value_on_a_group_node_is_value_not_allowed():
    provider = SchemaProviderMemory()
    provider.add_schema(GROUP_SCHEMA)
    errors = SchemaValidator(provider, True).validate(Parser().parse("Doc (com.example.group):\n\tMeta: x\n")[0])
    assert [(e.code, e.line) for e in errors] == [("VALUE_NOT_ALLOWED", 2)]
    errors = SchemaValidator(provider, True).validate(Parser().parse("Doc (com.example.group):\n\tMeta >>\n\t\tx\n")[0])
    assert [(e.code, e.line) for e in errors] == [("VALUE_NOT_ALLOWED", 2)]


def test_two_values_nodes_are_values_duplicated_with_the_line_of_the_second():
    text = ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tType: ENUM\n"
            "\t\tValues:\n\t\t\tValue: a\n\t\tValues:\n\t\t\tValue: b\n")
    # A provider reports it first as TOO_MANY_CHILDREN of the meta-schema (Values Max: 1)
    with pytest.raises(ValidationException) as info:
        SchemaProviderMemory().add_schema(text)
    assert info.value.code == "TOO_MANY_CHILDREN"
    # The transform itself reports VALUES_DUPLICATED, pointing at the second Values node
    with pytest.raises(ValidationException) as info:
        transform_node_to_schema(Parser().parse(text)[0])
    assert (info.value.code, info.value.line) == ("VALUES_DUPLICATED", 6)


@pytest.mark.parametrize("text,code,line", [
    ("Doc (@stxt.schema): com.example.x\n", "SCHEMA_ROOT_NOT_VALID", 1),
    ("Schema (com.example.x): com.example.x\n", "SCHEMA_ROOT_NOT_VALID", 1),
    ("Schema (@stxt.schema): nodots\n", "SCHEMA_ROOT_NOT_VALID", 1),
    ("Schema (@stxt.schema):\n", "SCHEMA_NAMESPACE_EMPTY", 1),
    ("Schema (@stxt.schema): com.example.x\n\tNode >>\n\t\tA\n", "SCHEMA_NODE_NOT_INLINE", 2),
    ("Schema (@stxt.schema): com.example.x\n\tNode: A\n\t\tChildren >>\n", "SCHEMA_NODE_NOT_INLINE", 3),
])
def test_schema_transform_root_and_form_errors(text, code, line):
    with pytest.raises(ValidationException) as info:
        transform_node_to_schema(Parser().parse(text)[0])
    assert (info.value.code, info.value.line) == (code, line), repr(info.value)
