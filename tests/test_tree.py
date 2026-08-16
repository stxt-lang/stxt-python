"""STXT-TREE-SPEC conformance: every source fixture of conformance/tree is parsed to the shared
canonical JSON tree. The comparison is semantic JSON, never whitespace."""

import json

import pytest

from stxt import Parser, to_canonical_json, to_canonical_tree

from .corpus import corpus_files, read, relative

DIRECTORY = "conformance/tree"
FILES = corpus_files([DIRECTORY])


def test_the_tree_corpus_is_not_empty():
    assert FILES, f"no .stxt file found in {DIRECTORY}"


@pytest.mark.parametrize("file", FILES, ids=relative)
def test_matches(file):
    expected_file = file.with_suffix(".json")
    assert expected_file.exists(), f"{relative(file)}: missing {expected_file.name}"

    nodes = Parser().parse(read(file))
    expected = json.loads(read(expected_file))

    assert to_canonical_tree(nodes) == expected
    assert json.loads(to_canonical_json(nodes)) == expected
