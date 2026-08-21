"""The 0.7.0 node model: two forms, each owning only what is its own; parent links with
integrity; derived level; declared vs effective namespace; mutability. Mirrors node.test.ts of
the TypeScript port and NodeTest of the Java port."""

import pytest

from stxt import NO_LINE, InlineNode, Node, NodeWriter, ParseException, Parser, RuntimeException, TextNode, to_canonical_json


# ---------------------------------------------------------------- forms

def test_two_forms_with_their_own_content():
    inline = InlineNode("Title", "  Hello  ")
    text = TextNode("Body", "line 1\nline 2")

    assert inline.is_text_node() is False
    assert inline.get_value() == "Hello"
    assert inline.get_text() == "Hello"

    assert text.is_text_node() is True
    assert list(text.get_text_lines()) == ["line 1", "line 2"]
    assert text.get_text() == "line 1\nline 2"


def test_each_form_owns_only_what_is_really_its_own():
    for member in ("get_children", "get_child", "get_value", "get_text_lines"):
        assert not hasattr(Node, member)
    assert not hasattr(TextNode, "get_children")
    assert not hasattr(InlineNode, "get_text_lines")

    # Walking a tree asks for the form
    root = InlineNode("Doc")
    root.add_text_node("Text", "t")
    root.add_inline_node("Inline")
    inline = sum(isinstance(c, InlineNode) for c in root.get_children())
    text = sum(isinstance(c, TextNode) for c in root.get_children())
    assert (inline, text) == (1, 1)


def test_the_hierarchy_is_closed():
    with pytest.raises(TypeError):
        class Other(Node):  # noqa: F811
            pass
    with pytest.raises(TypeError):
        Node("X", None, NO_LINE)  # abstract


def test_a_text_node_splits_at_lf_and_crlf_and_keeps_a_trailing_empty_line():
    text = TextNode("Body", "a\r\nb\n")
    assert list(text.get_text_lines()) == ["a", "b", ""]

    text.set_text("x")
    assert list(text.get_text_lines()) == ["x"]
    text.add_text_line("y")
    text.set_text_lines(["p", "q"])
    assert text.get_text() == "p\nq"
    text.clear_text()
    assert text.get_text() == ""

    assert list(TextNode("T", ["l1", "l2"]).get_text_lines()) == ["l1", "l2"]
    assert list(TextNode("T", text=["a"], namespace="com.x.y").get_text_lines()) == ["a"]


# ---------------------------------------------------------------- parent links

def test_add_child_links_both_ends_and_derives_the_level():
    root = InlineNode("Doc")
    child = root.add_inline_node("Child", "v")
    grandchild = child.add_text_node("Text", "t")

    assert child.get_parent() is root
    assert grandchild.get_parent() is child
    assert root.get_parent() is None
    assert (root.get_level(), child.get_level(), grandchild.get_level()) == (0, 1, 2)
    assert list(root.get_children()) == [child]


def test_a_node_cannot_have_two_parents():
    a = InlineNode("A")
    b = InlineNode("B")
    child = a.add_inline_node("Child")

    with pytest.raises(RuntimeException) as info:
        b.add_child(child)
    assert info.value.code == "NODE_ALREADY_ATTACHED"
    assert child.get_parent() is a, "the failed add changes nothing"
    assert len(b.get_children()) == 0


def test_remove_child_and_detach_unlink_both_ends():
    a = InlineNode("A")
    b = InlineNode("B")
    child = a.add_inline_node("Child")

    assert a.remove_child(child) is True
    assert child.get_parent() is None
    assert len(a.get_children()) == 0
    assert a.remove_child(child) is False, "not a child any more"
    assert b.remove_child(child) is False, "never was a child of b"

    b.add_child(child)
    assert child.get_parent() is b
    assert child.detach() is True
    assert child.get_parent() is None
    assert child.detach() is False, "already a root"


def test_remove_child_uses_identity_not_equality():
    root = InlineNode("Doc")
    first = root.add_inline_node("Item", "same")
    second = root.add_inline_node("Item", "same")

    assert root.remove_child(second) is True
    assert list(root.get_children()) == [first]
    assert first.get_parent() is root


def test_add_child_at_an_index_and_reorder():
    root = InlineNode("Doc")
    a = root.add_inline_node("A")
    c = root.add_inline_node("C")
    b = InlineNode("B")
    root.add_child(b, 1)
    assert list(root.get_children()) == [a, b, c]

    c.detach()
    root.add_child(c, 0)
    assert list(root.get_children()) == [c, a, b]

    with pytest.raises(IndexError):
        root.add_child(InlineNode("X"), 7)


def test_the_children_view_is_read_only():
    root = InlineNode("Doc")
    root.add_inline_node("A")
    view = root.get_children()
    with pytest.raises((AttributeError, TypeError)):
        view.append(InlineNode("B"))  # type: ignore[attr-defined]
    assert len(root.get_children()) == 1


def test_cycles_are_rejected():
    root = InlineNode("Doc")
    child = root.add_inline_node("Child")
    grandchild = child.add_inline_node("Grandchild")

    with pytest.raises(RuntimeException) as info:
        root.add_child(root)
    assert info.value.code == "NODE_CYCLE"
    with pytest.raises(RuntimeException) as info:
        grandchild.add_child(root)
    assert info.value.code == "NODE_CYCLE"


# ---------------------------------------------------------------- namespaces

def test_the_effective_namespace_is_inherited_through_the_parent_chain():
    root = InlineNode("Doc", "com.example.docs", "x")
    child = root.add_inline_node("Child")
    text = child.add_text_node("Text", "t")
    other = root.add_inline_node("Other", "org.other.ns", None)

    assert root.get_declared_namespace() == "com.example.docs"
    assert child.get_declared_namespace() == ""
    assert child.get_namespace() == "com.example.docs"
    assert text.get_namespace() == "com.example.docs"
    assert other.get_namespace() == "org.other.ns"
    assert child.get_qualified_name() == "com.example.docs:child"


def test_changing_a_declared_namespace_changes_the_whole_inheriting_subtree():
    root = InlineNode("Doc", "com.example.docs", "x")
    child = root.add_inline_node("Child")
    own = root.add_inline_node("Own", "org.other.ns", None)

    root.set_namespace("com.example.v2")
    assert child.get_namespace() == "com.example.v2"
    assert own.get_namespace() == "org.other.ns", "a declared namespace is not affected"

    root.set_namespace(None)
    assert root.get_namespace() == ""
    assert child.get_namespace() == ""


def test_moving_a_subtree_inherits_the_new_parents_namespace_and_detaching_loses_it():
    a = InlineNode("A", "com.a.ns", None)
    b = InlineNode("B", "com.b.ns", None)
    child = a.add_inline_node("Child")
    assert child.get_namespace() == "com.a.ns"

    child.detach()
    assert child.get_namespace() == ""

    b.add_child(child)
    assert child.get_namespace() == "com.b.ns"


def test_the_namespace_is_lower_cased_and_validated():
    n = InlineNode("Doc", "Com.Example", None)
    assert n.get_declared_namespace() == "com.example"
    with pytest.raises(ParseException) as info:
        n.set_namespace("nodots")
    assert info.value.code == "INVALID_NAMESPACE"
    with pytest.raises(ParseException):
        InlineNode("Doc", "bad namespace", None)


def test_parsed_trees_expose_declared_and_effective_namespaces_parents_and_levels():
    doc = Parser().parse("Doc (com.example.docs): x\n\tChild: y\n\t\tOther (org.other.ns): z\n\t\t\tDeep: w\n")[0]
    child = doc.get_children()[0]
    other = child.get_children()[0]
    deep = other.get_children()[0]

    assert doc.get_declared_namespace() == "com.example.docs"
    assert child.get_declared_namespace() == ""
    assert child.get_namespace() == "com.example.docs"
    assert other.get_declared_namespace() == "org.other.ns"
    assert deep.get_namespace() == "org.other.ns"
    assert child.get_parent() is doc
    assert deep.get_parent() is other
    assert deep.get_level() == 3


# ---------------------------------------------------------------- name, value, line

def test_name_value_and_line_are_mutable():
    n = InlineNode("Título  Largo", "v")
    assert n.get_name() == "Título Largo"
    assert n.get_canonical_name() == "título-largo"
    assert n.get_line() == NO_LINE
    assert n.get_line() == Node.NO_LINE

    n.set_name("Otro nombre")
    assert n.get_canonical_name() == "otro-nombre"
    n.set_value(None)
    assert n.get_value() == ""
    n.set_line(42)
    assert n.get_line() == 42

    with pytest.raises(ParseException) as info:
        n.set_name("Invalid!")
    assert info.value.code == "INVALID_NODE_NAME"
    assert n.get_name() == "Otro nombre", "the failed rename changes nothing"


def test_the_parser_sets_the_line_and_code_built_nodes_have_none():
    parsed = Parser().parse("Doc: x\n\tChild: y\n")[0].get_children()[0]
    assert parsed.get_line() == 2
    assert TextNode("T").get_line() == NO_LINE


def test_get_canonical_name_folds_case_and_separators():
    n = InlineNode("Año Nuevo")
    assert n.get_canonical_name() == "año-nuevo"


def test_constructor_shapes():
    assert InlineNode("A").get_value() == ""
    assert InlineNode("A", "v").get_value() == "v"
    n = InlineNode("A", "com.x.y", "v")
    assert (n.get_declared_namespace(), n.get_value(), n.get_line()) == ("com.x.y", "v", NO_LINE)
    n = InlineNode("A", "com.x.y", "v", 7)
    assert n.get_line() == 7
    n = InlineNode("A", value="v", namespace="com.x.y", line=3)
    assert (n.get_declared_namespace(), n.get_value(), n.get_line()) == ("com.x.y", "v", 3)
    with pytest.raises(TypeError):
        InlineNode("A", "b", "c", 1, "extra")


# ---------------------------------------------------------------- lookups

def test_child_lookups_use_the_effective_namespace():
    root = InlineNode("Doc", "com.example.docs", None)
    root.add_inline_node("Item", "1")
    root.add_inline_node("Item", "2")
    foreign = root.add_inline_node("Item", "org.other.ns", "3")
    root.add_text_node("Text", "t")

    assert len(root.get_children_by_name("item")) == 2
    assert root.get_children_by_name("Item", "org.other.ns") == [foreign]
    with pytest.raises(RuntimeException) as info:
        root.get_child("Item")
    assert info.value.code == "AMBIGUOUS_CHILD"
    assert root.get_child("Missing") is None
    assert root.get_child("Text").get_text() == "t"
    assert root.get_child("TEXT") is root.get_child("text"), "lookups are canonical"


# ---------------------------------------------------------------- built trees behave like parsed ones

def test_a_tree_built_by_code_writes_and_reparses_to_the_same_canonical_tree():
    doc = InlineNode("Email", "com.example.docs", "Weekly report")
    doc.add_inline_node("From", "ana@example.com")
    to = doc.add_inline_node("To")
    to.add_inline_node("Address", "bob@example.com")
    doc.add_text_node("Body", "Hi Bob,\n\nSee attached.\n")
    doc.add_inline_node("Cc", "org.other.ns", "x")

    written = NodeWriter.to_stxt(doc)
    reparsed = Parser().parse(written)

    assert to_canonical_json([doc]) == to_canonical_json(reparsed)
    assert "Email (com.example.docs): Weekly report" in written
    assert "\tCc (org.other.ns): x" in written, "the namespace is written where declared"
    assert "From (com.example.docs)" not in written, "inherited namespaces are implicit"
