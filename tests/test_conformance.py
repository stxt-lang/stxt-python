"""The STXT conformance kit: ``conformance/manifest.json`` of stxt-lang lists every case with its
category and expected result, so that any implementation can run the same cases with a small
runner like this one.

- ``tree``: the input parses and its canonical tree (STXT-TREE-SPEC) equals the expected JSON
  file, compared as a JSON value.
- ``parse-error``: the input is rejected, and the first error carries the expected code and
  line (STXT-SPEC 11.1).
- ``validate``: with every set of definitions, the input validates with no error.
- ``validate-error``: with every set of definitions, the first validation error carries the
  expected code and line (STXT-SCHEMA-SPEC 13.1).
- ``definition-error``: loading the input as a schema or a template fails with the expected
  code and line (STXT-SCHEMA-SPEC 13.1, STXT-TEMPLATE-SPEC 14.1).
"""

import json
import re

import pytest

from stxt import (ParseException, Parser, SchemaProviderMemory, SchemaValidator, TemplateSchemaProviderMemory,
                  ValidationException, to_canonical_json, to_canonical_tree)

from .corpus import STXT_LANG

DIRECTORY = STXT_LANG / "conformance"
MANIFEST = json.loads((DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
CASES = MANIFEST["cases"]


def _read(file):
    return (DIRECTORY / file).read_text(encoding="utf-8", newline="")


def _load_definitions(files, kinds=None):
    """A provider holding the given definition files: schemas first, templates on top."""
    schemas = SchemaProviderMemory()
    templates = TemplateSchemaProviderMemory(schemas)
    for file in files:
        kind = (kinds or {}).get(file) or ("schema" if file.endswith(".schema.stxt") else "template" if file.endswith(".template.stxt") else None)
        assert kind, f"{file}: a definition file must end in .schema.stxt or .template.stxt"
        (schemas.add_schema if kind == "schema" else templates.add_template)(_read(file))
    return templates


def _first_validation_error(text, provider):
    validator = SchemaValidator(provider, True)
    for node in Parser().parse(text):
        errors = validator.validate(node)
        if errors:
            return {"code": errors[0].code, "line": errors[0].line}
    return None


def test_declares_a_kit_version_and_the_specifications_it_covers():
    assert re.fullmatch(r"\d+\.\d+", MANIFEST["kit"])
    assert MANIFEST["specifications"]["STXT-SPEC"] == "1.0"
    assert MANIFEST["specifications"]["STXT-TREE-SPEC"] == "1.0"
    assert CASES


def test_lists_every_case_file_and_every_case_exactly_once():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    listed = {c["input"] for c in CASES}
    for sub in ("tree", "parse", "validate", "definition-errors"):
        for file in sorted((DIRECTORY / sub).glob("*.stxt")):
            assert f"{sub}/{file.name}" in listed, f"{sub}/{file.name} is not in the manifest"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case(case):
    text = _read(case["input"])
    if case["category"] == "tree":
        nodes = Parser().parse(text)
        expected = json.loads(_read(case["expected"]))
        assert to_canonical_tree(nodes) == expected
        assert json.loads(to_canonical_json(nodes)) == expected
    elif case["category"] == "parse-error":
        with pytest.raises(ParseException) as info:
            Parser().parse(text)
        assert {"code": info.value.code, "line": info.value.line} == case["error"]
    elif case["category"] in ("validate", "validate-error"):
        for definitions in case["definitions"]:
            actual = _first_validation_error(text, _load_definitions(definitions))
            where = f"{case['id']} with {definitions}"
            if case["category"] == "validate":
                assert actual is None, f"{where}: {actual}"
            else:
                assert actual == case["error"], where
    elif case["category"] == "definition-error":
        with pytest.raises((ValidationException, ParseException)) as info:
            _load_definitions([case["input"]], {case["input"]: case["kind"]})
        assert {"code": info.value.code, "line": info.value.line} == case["error"]
    else:
        pytest.fail(f"{case['id']}: unknown category {case['category']}")
