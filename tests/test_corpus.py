"""The corpus is mandatory: this suite documents the rule and fails if it is missing."""

from .corpus import DOC_DIRS, SCHEMA_DIRS, STXT_LANG, corpus_files


def test_the_mandatory_corpus_of_stxt_lang_is_found():
    assert (STXT_LANG / ".stxt").is_dir()
    assert (STXT_LANG / "conformance" / "tree").is_dir()


def test_the_corpus_is_not_empty():
    assert corpus_files(SCHEMA_DIRS), "no .stxt file found in " + ", ".join(SCHEMA_DIRS)
    assert corpus_files(DOC_DIRS), "no .stxt file found in " + ", ".join(DOC_DIRS)
