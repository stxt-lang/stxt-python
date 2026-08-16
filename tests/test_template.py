"""STXT-TEMPLATE-SPEC: the Structure grammar, cardinalities, references, ENUM values,
descriptions, and the equivalence with the schema it compiles to."""

import pytest

from stxt import (
    IndentStyle,
    NodeWriter,
    Parser,
    SchemaProviderMemory,
    SchemaValidator,
    TemplateSchemaProviderMemory,
    ValidationException,
    transform_template_node_to_schema,
)
from stxt.template import parse_child_line

TEMPLATE = """Template (@stxt.template): com.example.blog
	Description >>
		Post: A blog post
		Comment >>
			A comment,
			possibly nested
	Structure >>
		Post (com.example.blog):
			Title: (1) TEXT
			Date: (?) DATE
			Tags: (?) GROUP
				Tag: (+) ENUM [tech, life, misc]
			Body: (1) BLOCK
			Comment: (*)
				Author: (1)
				Text: (1) TEXT
				Comment: (*) @Comment
			Ref (com.example.other): (0,3)
"""

SCHEMA = """Schema (@stxt.schema): com.example.blog
	Description: A blog post
	Node: Post
		Children:
			Child: Title
				Min: 1
				Max: 1
			Child: Date
				Max: 1
			Child: Tags
				Max: 1
			Child: Body
				Min: 1
				Max: 1
			Child: Comment
			Child: Ref (com.example.other)
				Min: 0
				Max: 3
	Node: Title
		Type: TEXT
	Node: Date
		Type: DATE
	Node: Tags
		Type: GROUP
		Children:
			Child: Tag
				Min: 1
	Node: Tag
		Type: ENUM
		Values:
			Value: tech
			Value: life
			Value: misc
	Node: Body
		Type: BLOCK
	Node: Comment
		Children:
			Child: Author
				Min: 1
				Max: 1
			Child: Text
				Min: 1
				Max: 1
			Child: Comment
	Node: Author
	Node: Text
		Type: TEXT
"""

DOCS = [
    ("Post (com.example.blog):\n\tTitle: Hi\n\tBody >>\n\t\tx\n\tComment:\n\t\tAuthor: a\n\t\tText: t\n\t\tComment:\n\t\t\tAuthor: b\n\t\t\tText: u\n", []),
    ("Post (com.example.blog):\n\tTitle: Hi\n\tTags:\n\t\tTag: tech\n\t\tTag: rock\n\tBody >>\n", ["INVALID_VALUE"]),
    ("Post (com.example.blog):\n\tBody: inline\n", ["BLOCK_FORM_REQUIRED", "INVALID_NUMBER"]),
    ("Post (com.example.blog):\n\tTitle: a\n\tTitle: b\n\tBody >>\n\tExtra: no\n", ["CHILD_NOT_DECLARED", "NODE_NOT_EXIST_IN_SCHEMA", "INVALID_NUMBER", "INVALID_NUMBER", "INVALID_NUMBER"]),
]


def _compile(text):
    return transform_template_node_to_schema(Parser().parse(text)[0])


def test_the_template_compiles_to_the_equivalent_schema_model():
    schema = _compile(TEMPLATE)
    assert schema.get_namespace() == "com.example.blog"
    assert list(schema.get_nodes()) == ["post", "title", "date", "tags", "tag", "body", "comment", "author", "text"]

    post = schema.get_node_definition("Post")
    assert post.get_type() == "INLINE"
    assert post.get_description() == "A blog post"
    children = post.get_children()
    assert list(children) == ["com.example.blog:title", "com.example.blog:date", "com.example.blog:tags",
                              "com.example.blog:body", "com.example.blog:comment", "com.example.other:ref"]
    assert (children["com.example.blog:title"].get_min(), children["com.example.blog:title"].get_max()) == (1, 1)
    assert (children["com.example.blog:date"].get_min(), children["com.example.blog:date"].get_max()) == (None, 1)
    assert (children["com.example.blog:comment"].get_min(), children["com.example.blog:comment"].get_max()) == (None, None)
    assert (children["com.example.other:ref"].get_min(), children["com.example.other:ref"].get_max()) == (0, 3)

    tag = schema.get_node_definition("Tag")
    assert tag.get_type() == "ENUM" and tag.get_values() == ["tech", "life", "misc"]
    tags = schema.get_node_definition("tags")
    assert tags.get_children()["com.example.blog:tag"].get_min() == 1

    comment = schema.get_node_definition("Comment")
    assert comment.get_description() == "A comment,\npossibly nested"
    assert "com.example.blog:comment" in comment.get_children(), "the recursive reference declares the child"


@pytest.mark.parametrize("doc,expected", DOCS)
def test_template_and_schema_validate_documents_the_same(doc, expected):
    from_template = TemplateSchemaProviderMemory()
    from_template.add_template(TEMPLATE)
    from_schema = SchemaProviderMemory()
    from_schema.add_schema(SCHEMA)

    node = Parser().parse(doc)[0]
    a = sorted((e.code, e.line) for e in SchemaValidator(from_template, True).validate(node))
    b = sorted((e.code, e.line) for e in SchemaValidator(from_schema, True).validate(node))
    assert a == b
    assert sorted(c for c, _ in a) == sorted(expected)


def _template_error(structure_lines, description_lines=None):
    text = "Template (@stxt.template): com.example.t\n"
    if description_lines:
        text += "\tDescription >>\n" + "".join(f"\t\t{line}\n" for line in description_lines)
    text += "\tStructure >>\n" + "".join(f"\t\t{line}\n" for line in structure_lines)
    with pytest.raises(ValidationException) as info:
        TemplateSchemaProviderMemory().add_template(text)
    return info.value


@pytest.mark.parametrize("lines,code", [
    (["Root >>"], "INVALID_CHILD_LINE"),
    (["Root:", "\tChild >>"], "INVALID_CHILD_LINE"),
    (["Root: (x)"], "INVALID_CHILD_COUNT"),
    (["Root: (2,1)"], "MIN_GREATER_THAN_MAX"),
    (["Root: (1,2,3)"], "INVALID_CHILD_COUNT"),
    (["Root: (-1)"], "INVALID_CHILD_COUNT"),
    (["Root: FOO"], "TYPE_NOT_VALID"),
    (["Root: ENUM"], "VALUES_EMPTY_FOR_ENUM"),
    (["Root: ENUM []"], "VALUES_EMPTY_FOR_ENUM"),
    (["Root: ENUM [a, a]"], "VALUE_DUPLICATED"),
    (["Root: TEXT [a, b]"], "VALUES_ONLY_SUPPORTED_BY_ENUM"),
    (["Root: TEXT", "\tChild:"], "CHILDREN_NOT_ALLOWED_FOR_TYPE"),
    (["Root:", "\tA:", "Root:"], "NODE_DEFINED_MULTIPLE_TIMES"),
    (["Root:", "\tA:", "\tA:"], "CHILD_DEF_ALREADY_DEFINED"),
    (["Root:", "\tA:", "\tB:", "\t\tA: @Other"], "NODE_REFERENCE_NOT_VALID"),
    (["Root:", "\tA:", "\tB:", "\t\tA: @A TEXT"], "REFERENCE_WITH_TYPE_NOT_ALLOWED"),
    (["Root:", "\tA:", "\tB:", "\t\tA: @A [x]"], "VALUES_NOT_ALLOWED_IN_REFERENCE"),
    (["Root:", "\tA:", "\tB:", "\t\tA: @A", "\t\t\tC:"], "CHILDREN_NOT_ALLOWED_IN_REFERENCE"),
    (["Root:", "\tC: @C"], "REFERENCE_NOT_FOUND"),
    (["Root:", "\tA: @Nowhere"], "REFERENCE_NOT_FOUND"),
    (["Root:", "\tExt (com.example.o): TEXT"], "TYPE_DEFINITION_NOT_ALLOWED"),
    (["Root:", "\tExt (com.example.o): [a]"], "VALUES_NOT_ALLOWED_IN_EXTERNAL_NAMESPACE"),
    (["Root:", "\tExt (com.example.o):", "\t\tB:"], "CHILDREN_NOT_ALLOWED_IN_EXTERNAL_NAMESPACE"),
])
def test_template_structure_errors(lines, code):
    assert _template_error(lines).code == code


@pytest.mark.parametrize("description,code", [
    (["Missing: x"], "NODE_NOT_FOUND"),
    (["Root: x", "Root: y"], "DESCRIPTION_ALREADY_DEFINED"),
    (["Root (com.example.o): x"], "EXTERNAL_DESCRIPTION_NOT_ALLOWED"),
    (["Root: x", "\tChild: y"], "CHILDREN_DESCRIPTION_NOT_ALLOWED"),
])
def test_template_description_errors(description, code):
    assert _template_error(["Root:"], description).code == code


def test_errors_inside_structure_point_at_the_line_of_the_original_document():
    error = _template_error(["Root:", "\tA:", "\tB: FOO"])
    # line 1 = Template, 2 = Structure >>, 3 = Root, 4 = A, 5 = B
    assert (error.code, error.line) == ("TYPE_NOT_VALID", 5)
    assert isinstance(error.with_line(9), ValidationException), "the subtype is preserved"


def test_a_template_without_structure_is_rejected():
    with pytest.raises(ValidationException) as info:
        TemplateSchemaProviderMemory().add_template("Template (@stxt.template): com.example.t\n\tDescription: x\n")
    assert info.value.code in ("TEMPLATE_STRUCTURE_REQUIRED", "INVALID_NUMBER")


def test_open_ancestor_recursion_and_references_to_closed_definitions():
    schema = _compile("Template (@stxt.template): com.example.r\n\tStructure >>\n\t\tA:\n\t\t\tB:\n\t\t\t\tA: (?) @A\n\t\t\t\tC: TEXT\n\t\t\tD:\n\t\t\t\tC: (1) @C\n")
    assert schema.get_node_definition("B").get_children()["com.example.r:a"].get_max() == 1
    assert schema.get_node_definition("D").get_children()["com.example.r:c"].get_min() == 1
    assert schema.get_node_definition("C").get_type() == "TEXT"


@pytest.mark.parametrize("raw,expected", [
    ("", (None, None, None, None)),
    ("(1)", (None, 1, 1, None)),
    ("(?) TEXT", ("TEXT", None, 1, None)),
    ("(*)", (None, None, None, None)),
    ("(+)", (None, 1, None, None)),
    ("(2+)", (None, 2, None, None)),
    ("(3-)", (None, None, 3, None)),
    ("(1,4) NATURAL", ("NATURAL", 1, 4, None)),
    ("(1) ENUM [a, b]", ("ENUM", 1, 1, ["a", "b"])),
    ("ENUM []", ("ENUM", None, None, [])),
    ("@Body Content", ("@Body Content", None, None, None)),
    ("  ( 2 )   TEXT  ", ("TEXT", 2, 2, None)),
])
def test_child_line_parser(raw, expected):
    cl = parse_child_line(raw, 1)
    assert (cl.get_type(), cl.get_min(), cl.get_max(), cl.get_values()) == expected


def test_writer_keeps_a_template_readable():
    docs = Parser().parse(TEMPLATE)
    written = NodeWriter.to_stxt_docs(docs, IndentStyle.SPACES_4)
    # The block content keeps its own (relative) indentation literally: tabs inside stay tabs
    assert "    Structure >>\n        Post (com.example.blog):\n        \tTitle: (1) TEXT\n" in written
    assert _compile(written).get_nodes().keys() == _compile(TEMPLATE).get_nodes().keys()
