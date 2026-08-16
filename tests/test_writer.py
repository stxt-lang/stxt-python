"""Writer regression: writing a parsed document and parsing it again must neither lose nor
change anything, with both indentation styles, over the whole stxt-web corpus."""

import pytest

from stxt import IndentStyle, NodeWriter, Parser, to_canonical_tree

from .corpus import DOC_DIRS, SCHEMA_DIRS, corpus_files, describe_errors, read, relative

FILES = corpus_files(SCHEMA_DIRS) + corpus_files(DOC_DIRS)


@pytest.mark.parametrize("style", [IndentStyle.TABS, IndentStyle.SPACES_4], ids=lambda s: s.value)
@pytest.mark.parametrize("file", FILES, ids=relative)
def test_round_trip_is_stable(file, style):
    name = relative(file)
    original = Parser().parse_result(read(file))
    assert len(original.get_errors()) == 0, f"{name} does not parse:{describe_errors(original.get_errors())}"

    written = NodeWriter.to_stxt_docs(original.get_nodes(), style)

    reparsed = Parser().parse_result(written)
    assert len(reparsed.get_errors()) == 0, \
        f"{name}: the output of the writer does not parse again:{describe_errors(reparsed.get_errors())}"

    assert NodeWriter.to_stxt_docs(reparsed.get_nodes(), style) == written, \
        f"{name}: the tree changes when the output of the writer is parsed again"
    assert to_canonical_tree(reparsed.get_nodes()) == to_canonical_tree(original.get_nodes()), \
        f"{name}: the canonical tree changes through the writer"
