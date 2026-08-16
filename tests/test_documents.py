"""Validation regression: the real documents of stxt-web must parse with no errors and
validate with no warnings against the schemas/templates of stxt-web itself.

Also the schema <-> template equivalence: one same namespace is described twice in stxt-web,
as a schema and as a template; both must validate the documents exactly the same way.
"""

import pytest

from stxt import Parser

from .corpus import DOC_DIRS, corpus_files, describe_errors, load_provider, parse_with_schemas, read, relative

FILES = corpus_files(DOC_DIRS)
PROVIDER = load_provider()

FROM_SCHEMAS = load_provider([".stxt/schemas", "examples/definitions/tutorial"])
FROM_TEMPLATES = load_provider(["examples/definitions/templates", ".stxt/tutorial"])


@pytest.mark.parametrize("file", FILES, ids=relative)
def test_validates(file):
    name = relative(file)
    result = parse_with_schemas(read(file), PROVIDER)
    errors = result.get_errors()
    assert len(errors) == 0, f"{name} has {len(errors)} error(s):{describe_errors(errors)}"
    assert len(result.get_nodes()) > 0, f"{name} produced no node at all"


def test_every_document_declares_a_namespace_with_a_known_schema():
    # If this failed, the tests above would pass trivially: with no namespace the
    # ConditionalValidator validates nothing.
    for file in FILES:
        for node in Parser().parse_result(read(file)).get_nodes():
            namespace = node.get_namespace()
            name = f"{relative(file)} -> {node.get_name()}"
            assert namespace != "", f"{name}: document with no namespace"
            assert PROVIDER.get_schema(namespace) is not None, f"{name}: there is no schema for {namespace}"


def _comparable_files():
    # Only the documents whose namespace is described both ways are comparable.
    result = []
    for file in FILES:
        namespaces = [n.get_namespace() for n in Parser().parse_result(read(file)).get_nodes()]
        if namespaces and all(FROM_SCHEMAS.get_schema(ns) and FROM_TEMPLATES.get_schema(ns) for ns in namespaces):
            result.append(file)
    return result


COMPARABLE = _comparable_files()


def test_there_are_comparable_documents():
    assert COMPARABLE, "no document is described both as a schema and as a template"


@pytest.mark.parametrize("file", COMPARABLE, ids=relative)
def test_schema_and_template_validate_the_same(file):
    text = read(file)

    def codes(provider):
        return [f"[{e.code}] line {e.line}" for e in parse_with_schemas(text, provider).get_errors()]

    assert codes(FROM_TEMPLATES) == codes(FROM_SCHEMAS), \
        f"{relative(file)}: the template and the schema do not validate the same"
