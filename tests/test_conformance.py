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
- ``discovery``: a virtual file system and environment resolve to the expected chain, active
  definitions and resolution errors (STXT-DISCOVERY-SPEC).
- ``writer``: the root nodes of the input, written in canonical text form, equal the expected
  text in both styles (STXT-TREE-SPEC 11).
- ``format``: the input reformatted equals the expected text in both styles, with the expected
  syntax errors (STXT-TREE-SPEC 12).
"""

import json
import re

import pytest

from stxt import (DiscoveryResolver, Formatter, IndentStyle, NodeWriter, ParseException, Parser, SchemaProviderMemory,
                  SchemaValidator, TemplateSchemaProviderMemory, ValidationException, to_canonical_json,
                  to_canonical_tree)

from .discovery_memory import FakeEnvironment, MemoryFileSystem

from .corpus import STXT_LANG

DIRECTORY = STXT_LANG / "conformance"
MANIFEST = json.loads((DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
CASES = MANIFEST["cases"]
STYLES = [("tabs", IndentStyle.TABS), ("spaces", IndentStyle.SPACES_4)]


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


def test_declares_cumulative_profiles_that_cover_every_category():
    profiles = MANIFEST["profiles"]
    covered = set()
    for name, p in profiles.items():
        assert "includes" not in p or p["includes"] in profiles, f"profile {name} includes an unknown profile"
        assert all(s in MANIFEST["specifications"] for s in p["specifications"]), f"profile {name}: unknown specification"
        covered.update(p["categories"])
    assert {c["category"] for c in CASES} <= covered


def test_lists_every_case_file_and_every_case_exactly_once():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    listed = {c.get("input") for c in CASES}
    for sub in ("tree", "parse", "validate", "definition-errors", "format"):
        for file in sorted((DIRECTORY / sub).glob("*.stxt")):
            if file.name.endswith((".tabs.stxt", ".spaces.stxt")):
                continue
            assert f"{sub}/{file.name}" in listed, f"{sub}/{file.name} is not in the manifest"


def _discovery(case):
    fs = MemoryFileSystem({virtual: _read(real) for virtual, real in case["files"].items()})
    for directory in case.get("dirs", []):
        fs.add_empty_dir(directory)
    env = case["environment"]
    result = DiscoveryResolver(fs, FakeEnvironment(env["stxtPath"], env["userDir"], env["systemDir"])).resolve(case["documentDir"])
    expected = case["expected"]
    assert list(result.get_chain()) == expected["chain"], f"{case['id']}: chain"
    for namespace, file in expected["active"].items():
        definition = result.get_definition(namespace)
        assert (definition.file if definition else None) == file, f"{case['id']}: active definition of {namespace}"
        assert (result.get_schema(namespace) is not None) == (file is not None), f"{case['id']}: get_schema({namespace})"
    actual = [{"code": e.code, "file": e.file, "namespace": e.namespace} for e in result.get_errors()]
    assert len(actual) == len(expected["errors"]), f"{case['id']}: errors {actual}"
    for e in expected["errors"]:
        match = next((a for a in actual if a["code"] == e["code"] and e.get("file", a["file"]) == a["file"]
                      and e.get("namespace", a["namespace"]) == a["namespace"]), None)
        assert match, f"{case['id']}: missing error {e} in {actual}"
        actual.remove(match)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case(case):
    if case["category"] == "discovery":
        _discovery(case)
        return
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
    elif case["category"] == "writer":
        nodes = Parser().parse(text)
        for key, style in STYLES:
            assert NodeWriter.to_stxt_docs(nodes, style) == _read(case["expected"][key]), f"{case['id']}: {key}"
    elif case["category"] == "format":
        for key, style in STYLES:
            result = Formatter.format(text, style)
            assert result.text == _read(case["expected"][key]), f"{case['id']}: {key}"
            assert [{"code": e.code, "line": e.line} for e in result.errors] == case["errors"], f"{case['id']}: errors with {key}"
    elif case["category"] == "definition-error":
        with pytest.raises((ValidationException, ParseException)) as info:
            _load_definitions([case["input"]], {case["input"]: case["kind"]})
        assert {"code": info.value.code, "line": info.value.line} == case["error"]
    else:
        pytest.fail(f"{case['id']}: unknown category {case['category']}")
