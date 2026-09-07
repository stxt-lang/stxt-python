"""Hardening of the 2026-09-06 security review: every case here reproduced a pathological cost,
an escaping exception or a structure injection before the fix. Mirrors hardening.test.ts of the
TypeScript port and HardeningTest of the Java port."""

import os
import sys
import time

import pytest

from stxt import (
    DiscoveryEntry,
    DiscoveryResolver,
    InlineNode,
    Parser,
    RuntimeException,
    SchemaProviderMemory,
    SchemaValidator,
    TemplateSchemaProviderMemory,
    TextNode,
    UnifiedSchemaProvider,
    ValidationException,
)
from stxt.core.string_utils import lower_case
from stxt.discovery.discovery_environment import SystemDiscoveryEnvironment
from stxt.discovery.discovery_file_system import MAX_DEFINITION_FILE_BYTES, OsDiscoveryFileSystem
from stxt.template import parse_child_line

from .discovery_memory import FakeEnvironment, MemoryFileSystem


def _code(exc_info) -> str:
    return exc_info.value.code


# ---------------------------------------------------------------- template RuleSpec

def test_child_line_rejects_an_unclosed_list_of_blanks_in_milliseconds():
    for line in ("TEXT [" + " " * 9990 + "x", "[" + "\t " * 4995 + "x", "(" + " " * 9990 + "x"):
        start = time.perf_counter()
        with pytest.raises(ValidationException) as e:
            parse_child_line(line, 1)
        assert _code(e) == "STRUCTURE_LINE_NOT_VALID"
        assert time.perf_counter() - start < 1.0  # was minutes


@pytest.mark.parametrize("line, expected", [
    ("( 2 ) TEXT", ("TEXT", 2, 2, None)),
    ("  [a, b]  ", (None, None, None, ["a", "b"])),
    ("TEXT [ ]", ("TEXT", None, None, [])),
    ("(1,3) ENUM [ a , b ]", ("ENUM", 1, 3, ["a", "b"])),
    ("TEXT [a[b]", ("TEXT", None, None, ["a[b"])),
    ("(?)\t@Ref\t", ("@Ref", None, 1, None)),
])
def test_child_line_keeps_the_grammar_of_the_former_pattern(line, expected):
    c = parse_child_line(line, 1)
    assert (c.get_type(), c.get_min(), c.get_max(), c.get_values()) == expected


@pytest.mark.parametrize("line, expected", [
    ("()", "STRUCTURE_LINE_NOT_VALID"),
    ("( )", "STRUCTURE_LINE_NOT_VALID"),
    ("((1))", "STRUCTURE_LINE_NOT_VALID"),
    ("(1", "STRUCTURE_LINE_NOT_VALID"),
    ("TEXT (1)", "STRUCTURE_LINE_NOT_VALID"),
    ("(1) (2)", "STRUCTURE_LINE_NOT_VALID"),
    ("TEXT a]", "STRUCTURE_LINE_NOT_VALID"),
    ("TEXT [a", "STRUCTURE_LINE_NOT_VALID"),
    ("[a] b", "STRUCTURE_LINE_NOT_VALID"),
    ("[a] [b]", "STRUCTURE_LINE_NOT_VALID"),
    ("[a]]", "STRUCTURE_LINE_NOT_VALID"),
    ("(1[) TEXT", "CARDINALITY_NOT_VALID"),
    ("(x) TEXT", "CARDINALITY_NOT_VALID"),
])
def test_child_line_rejects_what_the_former_pattern_rejected(line, expected):
    with pytest.raises(ValidationException) as e:
        parse_child_line(line, 1)
    assert _code(e) == expected


# ---------------------------------------------------------------- cardinalities

def test_a_cardinality_of_more_digits_than_the_bound_is_rejected_before_int():
    digits = "1" * 5000
    with pytest.raises(ValidationException) as e:
        parse_child_line(f"({digits}) TEXT", 1)
    assert _code(e) == "CARDINALITY_NOT_VALID"

    schema = f"Schema (@stxt.schema): a.b\n\tNode: R\n\t\tChildren:\n\t\t\tChild: T\n\t\t\t\tMin: {digits}\n\tNode: T\n"
    with pytest.raises(ValidationException) as e:
        SchemaProviderMemory().add_schema(schema)
    assert _code(e) == "CARDINALITY_NOT_VALID"


# ---------------------------------------------------------------- ENUM

def test_an_enum_invalid_value_message_does_not_carry_the_list_of_values():
    values = "\n".join(f"\t\t\tValue: v{i}" for i in range(2000))
    provider = UnifiedSchemaProvider()
    provider.add_file(f"Schema (@stxt.schema): com.example.big\n\tNode: R\n\t\tChildren:\n\t\t\tChild: E\n"
                      f"\t\t\t\tMax: 5\n\tNode: E\n\t\tType: ENUM\n\t\tValues:\n{values}\n")
    parser = Parser()
    parser.register_validator(SchemaValidator(provider, False))

    result = parser.parse_result("R (com.example.big):\n\tE: zz\n\tE: v1\n")

    assert [e.code for e in result.get_errors()] == ["INVALID_VALUE"]
    assert len(result.get_errors()[0].message) < 100
    assert "'zz'" in result.get_errors()[0].message


def test_a_large_enum_loads_in_linear_time():
    values = "\n".join(f"\t\t\tValue: v{i}" for i in range(40000))
    start = time.perf_counter()
    SchemaProviderMemory().add_schema(f"Schema (@stxt.schema): a.b\n\tNode: E\n\t\tType: ENUM\n\t\tValues:\n{values}\n")
    assert time.perf_counter() - start < 3.0  # was 10 s


# ---------------------------------------------------------------- line breaks through the API

def test_inline_node_rejects_lf_and_keeps_a_lone_cr():
    with pytest.raises(RuntimeException) as e:
        InlineNode("A", "a\nb: injected")
    assert _code(e) == "LINE_BREAK_NOT_ALLOWED"
    node = InlineNode("A", "a")
    with pytest.raises(RuntimeException):
        node.set_value("x\ny")
    assert node.get_value() == "a"
    node.set_value("a\rb")
    assert node.get_value() == "a\rb"


def test_text_node_rejects_lf_in_a_line_and_splits_a_string_instead():
    with pytest.raises(RuntimeException) as e:
        TextNode("A", ["x\ny"])
    assert _code(e) == "LINE_BREAK_NOT_ALLOWED"
    node = TextNode("A", "x\ny")
    assert list(node.get_text_lines()) == ["x", "y"]
    with pytest.raises(RuntimeException):
        node.add_text_line("p\nq")
    with pytest.raises(RuntimeException):
        node.set_text_lines(["ok", "p\nq"])
    assert list(node.get_text_lines()) == ["x", "y"]
    node.add_text_line("z\r")
    assert list(node.get_text_lines()) == ["x", "y", "z\r"]


# ---------------------------------------------------------------- deep trees built by a program

def test_a_chain_of_100000_nodes_is_built_in_linear_time_and_resolves_its_namespace():
    root = InlineNode("Root", "a.b", None)
    node = root
    for _ in range(100000):
        child = InlineNode("N")
        node.add_child(child)
        node = child

    assert node.get_level() == 100000
    assert node.get_namespace() == "a.b"
    assert node.get_qualified_name() == "a.b:n"


def test_every_cycle_is_still_detected():
    root, child, grandchild = InlineNode("Root"), InlineNode("Child"), InlineNode("Grandchild")
    root.add_child(child)
    child.add_child(grandchild)
    for parent, node in ((root, root), (grandchild, root)):
        with pytest.raises(RuntimeException) as e:
            parent.add_child(node)
        assert _code(e) == "NODE_CYCLE"

    a, b = InlineNode("A"), InlineNode("B")
    a.add_child(b)
    with pytest.raises(RuntimeException) as e:
        b.add_child(a)
    assert _code(e) == "NODE_CYCLE"


# ---------------------------------------------------------------- parser input

def test_lines_are_split_lazily_at_lf_and_crlf_only():
    nodes = Parser().parse("A: one\rB: two\r\nC: three\n")
    assert [(n.get_name(), n.get_value()) for n in nodes] == [("A", "one\rB: two"), ("C", "three")]
    assert [n.get_name() for n in Parser().parse("A: 1\nB: 2")] == ["A", "B"]
    assert Parser().parse("") == []


@pytest.mark.parametrize("bad", [-2, 1.5, "10", None, True])
def test_a_limit_that_is_not_an_integer_ge_0_or_minus_1_is_rejected(bad):
    for name in ("max_nesting", "max_line_length", "max_input_size"):
        with pytest.raises(ValueError):
            Parser(**{name: bad})
    assert Parser(max_nesting=-1, max_line_length=0, max_input_size=-1).parse_result("").get_errors() == []


# ---------------------------------------------------------------- namespaces

def test_namespaces_are_checked_by_a_linear_scan():
    long = "a." * 1999 + "a"
    assert Parser().parse(f"N ({long}): v\n")[0].get_namespace() == long
    for bad in ("a", "@", "@a", "a.", ".a", "a..b", "a b.c", "a.b!"):
        with pytest.raises(Exception) as e:
            Parser().parse(f"N ({bad}): v\n")
        assert e.value.code in ("INVALID_NAMESPACE", "INVALID_LINE"), bad
    for good in ("a.b", "A.B", "@stxt.schema", "com.example.docs", "a1.2b"):
        assert Parser().parse(f"N ({good}): v\n")[0].get_namespace() == good.lower()


def test_namespaces_lower_case_ascii_only_kelvin_sign_is_not_a_k():
    with pytest.raises(Exception) as e:
        Parser().parse("N (Kelvin.x): v\n")
    assert e.value.code == "INVALID_NAMESPACE"
    with pytest.raises(Exception) as e:
        InlineNode("N", "Kelvin.x", "v")
    assert e.value.code == "INVALID_NAMESPACE"
    assert lower_case("Com.Example") == "com.example"
    assert lower_case("K") == "K"


# ---------------------------------------------------------------- discovery

class _CyclicFileSystem(MemoryFileSystem):
    """A level whose every directory lists the same two subdirectories: a cycle of breadth 2."""

    def __init__(self):
        super().__init__({})
        self.listings = 0

    def is_directory(self, path):
        return path.startswith("/p/.stxt")

    def list_directory(self, path):
        self.listings += 1
        return [DiscoveryEntry("/p/.stxt/a", "a", True), DiscoveryEntry("/p/.stxt/b", "b", True)]


def test_each_directory_of_a_level_is_visited_once():
    fs = _CyclicFileSystem()
    result = DiscoveryResolver(fs, FakeEnvironment()).resolve("/p")
    assert fs.listings == 3
    assert result.get_errors() == []


def test_an_adapter_whose_is_directory_raises_does_not_make_resolve_raise():
    fs = MemoryFileSystem({"/p/.stxt/x.stxt": "irrelevant"})
    fs.is_directory = lambda path: (_ for _ in ()).throw(OSError("boom"))
    resolver = DiscoveryResolver(fs, FakeEnvironment(["/etc/stxt"], "/home/u/.stxt", "/etc/stxt"))
    assert resolver.resolve_chain("/p") == []
    assert resolver.resolve("/p").get_errors() == []


@pytest.mark.parametrize("bad", [-1, 1.5, None, "3"])
def test_max_ascent_must_be_an_integer_ge_0(bad):
    with pytest.raises(ValueError):
        DiscoveryResolver(MemoryFileSystem({}), FakeEnvironment(), max_ascent=bad)


def test_empty_stxt_path_entries_are_dropped(monkeypatch):
    monkeypatch.setenv("STXT_PATH", os.pathsep + "/opt/defs" + os.pathsep + os.pathsep + "/x" + os.pathsep)
    assert SystemDiscoveryEnvironment().get_stxt_path() == ["/opt/defs", "/x"]
    monkeypatch.setenv("STXT_PATH", "")
    assert SystemDiscoveryEnvironment().get_stxt_path() == []


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX only")
def test_the_os_adapter_lists_only_regular_files_and_directories(tmp_path):
    level = tmp_path / ".stxt"
    level.mkdir()
    (level / "ok.stxt").write_text("Schema (@stxt.schema): a.b\n\tNode: R\n", encoding="utf-8")
    os.mkfifo(level / "pipe.stxt")  # open() would block forever without a writer
    names = sorted(entry.name for entry in OsDiscoveryFileSystem().list_directory(str(level)))
    assert names == ["ok.stxt"]


def test_the_os_adapter_rejects_a_definition_file_above_the_size_bound_without_reading_it(tmp_path):
    big = tmp_path / "big.stxt"
    with open(big, "wb") as f:
        f.truncate(MAX_DEFINITION_FILE_BYTES + 1)  # sparse: no bytes are written
    with pytest.raises(OSError):
        OsDiscoveryFileSystem().read_file(str(big))
    level = tmp_path / ".stxt"
    level.mkdir()
    with open(level / "big.stxt", "wb") as f:
        f.truncate(MAX_DEFINITION_FILE_BYTES + 1)
    result = DiscoveryResolver(OsDiscoveryFileSystem(), FakeEnvironment()).resolve(str(tmp_path))
    assert [e.code for e in result.get_errors()] == ["DISCOVERY_NOT_PARSEABLE"]
