"""Helpers for the regression tests against the real corpus in ``../stxt-lang``.

The corpus is deliberately not copied into this repository: stxt-lang is the normative source
of the language and the tests must fail when the implementation drifts away from the real
documents, not from a frozen copy.

The corpus is MANDATORY: if ``stxt-lang`` cannot be located, the corpus suites fail (they are
never skipped). Importing this module raises when the corpus is missing, so every suite that
depends on it fails at collection with a message that explains what is missing.
"""

from __future__ import annotations

import os
from pathlib import Path

from stxt import ParseException, ParseResult, Parser, SchemaValidator, UnifiedSchemaProvider

# Folders of stxt-lang holding schemas and templates (they are loaded into the provider).
SCHEMA_DIRS = [".stxt", "examples/definitions"]

# Folders of stxt-lang holding documents that must validate against those schemas.
DOC_DIRS = ["docs", "es", "en"]


class CorpusNotFound(Exception):
    """The mandatory corpus of the sibling project stxt-lang was not found."""


def find_stxt_lang() -> Path:
    """Locates ``stxt-lang``: ``STXT_LANG`` if set, otherwise the sibling ``../stxt-lang``.

    Raises:
        CorpusNotFound: the corpus is mandatory, never optional.
    """
    candidates = [
        os.environ.get("STXT_LANG"),
        # this file is <repo>/tests/corpus.py
        str(Path(__file__).resolve().parent.parent.parent / "stxt-lang"),
    ]
    for candidate in candidates:
        if candidate and (Path(candidate) / ".stxt").is_dir():
            return Path(candidate)

    tried = ", ".join(f'"{c}"' for c in candidates if c)
    raise CorpusNotFound(
        "The corpus of the sibling project stxt-lang is required and was not found. Tried: "
        + tried + ". Clone stxt-lang/stxt-lang next to this repository or set STXT_LANG=/path/to/stxt-lang.")


#: Root of stxt-lang. Importing this module fails loudly when the corpus is missing.
STXT_LANG = find_stxt_lang()


def find_stxt_files(directory: Path) -> list[Path]:
    """Every .stxt file under a directory, recursively and in a stable order."""
    if not directory.exists():
        return []
    return sorted(p for p in directory.rglob("*.stxt") if p.is_file())


def corpus_files(dirs: list[str]) -> list[Path]:
    """The .stxt files of the given folders (relative to the root of stxt-lang)."""
    result: list[Path] = []
    for directory in dirs:
        result.extend(find_stxt_files(STXT_LANG / directory))
    return result


def relative(path: Path) -> str:
    return str(path.relative_to(STXT_LANG))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_provider(dirs: list[str] = SCHEMA_DIRS) -> UnifiedSchemaProvider:
    """Loads into a provider every schema/template of the given folders."""
    provider = UnifiedSchemaProvider()
    for file in corpus_files(dirs):
        provider.add_file(read(file))
    return provider


def parse_with_schemas(text: str, provider: UnifiedSchemaProvider) -> ParseResult:
    """Parses a document validating it against the provider (only namespaced nodes)."""
    parser = Parser()
    parser.register_validator(SchemaValidator(provider))
    return parser.parse_result(text)


def describe_errors(errors: list[ParseException]) -> str:
    """Readable message for the assert: ``[CODE] line 12: message``."""
    return "".join(f"\n\t[{e.code}] line {e.line}: {e.message}" for e in errors)
