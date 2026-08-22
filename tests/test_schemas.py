"""Loading regression: every real schema and template of stxt-lang must parse, validate against
its meta-schema and be transformed into a Schema without exception."""

import pytest

from stxt import UnifiedSchemaProvider

from .corpus import SCHEMA_DIRS, corpus_files, read, relative

FILES = corpus_files(SCHEMA_DIRS)


@pytest.mark.parametrize("file", FILES, ids=relative)
def test_loads(file):
    # Each file in a provider of its own, so a failure points at the guilty file
    provider = UnifiedSchemaProvider()
    provider.add_file(read(file))
    assert len(provider.get_all_schemas()) > 0, \
        "the file produced no schema at all (root namespace other than @stxt.schema/@stxt.template?)"


def test_all_of_them_load_together_into_a_single_provider():
    provider = UnifiedSchemaProvider()
    for file in FILES:
        provider.add_file(read(file))
    # Schemas and templates share a namespace on purpose, so there are fewer schemas than files
    assert len(provider.get_all_schemas()) > 0
