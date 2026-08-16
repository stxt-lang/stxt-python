"""Providers: in-memory schema/template providers, meta providers, and the SchemaProvider
contract (never throw "not found"; SCHEMA_NOT_FOUND is a finding of SchemaValidator)."""

import pytest

from stxt import (
    MetaTemplateSchemaProvider,
    Parser,
    SchemaProviderMemory,
    SchemaProviderMeta,
    SchemaValidator,
    TemplateSchemaProviderMemory,
    UnifiedSchemaProvider,
    ValidationException,
)

# Passes the parser and the transform, but Type: FOO violates the meta-schema ENUM
INVALID_SCHEMA = "Schema (@stxt.schema): com.example.demo\n\tNode: Root\n\t\tType: FOO\n"
VALID_SCHEMA = "Schema (@stxt.schema): com.example.demo\n\tNode: Root\n\t\tType: TEXT\n"

# Parses fine and the transform ignores the extra child, but the meta-template's closed
# content model does not declare "Foo" under Template
INVALID_TEMPLATE = "Template (@stxt.template): com.example.demo\n\tStructure >>\n\t\tRoot:\n\tFoo: bar\n"
VALID_TEMPLATE = "Template (@stxt.template): com.example.demo\n\tStructure >>\n\t\tRoot:\n"


class TestSchemaProviderMemory:
    def test_throws_the_first_validation_error_for_an_invalid_schema_and_does_not_register_it(self):
        provider = SchemaProviderMemory()
        with pytest.raises(ValidationException):
            provider.add_schema(INVALID_SCHEMA)
        assert provider.get_all_schemas() == []

    def test_still_registers_a_valid_schema(self):
        provider = SchemaProviderMemory()
        provider.add_schema(VALID_SCHEMA)
        assert len(provider.get_all_schemas()) == 1
        assert provider.get_schema("com.example.demo") is not None
        assert provider.get_schema("COM.Example.demo") is not None, "namespaces are case-insensitive"
        provider.clear()
        assert provider.get_all_schemas() == []
        assert provider.get_schema("@stxt.schema") is not None, "the parent is left untouched"

    def test_rejects_a_schema_node_whose_value_is_not_a_valid_stxt_node_name(self):
        with pytest.raises(ValidationException) as info:
            SchemaProviderMemory().add_schema("Schema (@stxt.schema): com.example.demo\n\tNode: Invalid!\n")
        assert info.value.code == "INVALID_NODE_NAME"

    def test_rejects_a_schema_child_whose_value_is_not_a_valid_stxt_node_name(self):
        text = "Schema (@stxt.schema): com.example.demo\n\tNode: Root\n\t\tChildren:\n\t\t\tChild: Invalid!\n"
        with pytest.raises(ValidationException) as info:
            SchemaProviderMemory().add_schema(text)
        assert info.value.code == "INVALID_NODE_NAME"

    def test_rejects_two_documents_in_one_text(self):
        with pytest.raises(ValidationException) as info:
            SchemaProviderMemory().add_schema(VALID_SCHEMA + VALID_SCHEMA)
        assert info.value.code == "INVALID_SCHEMA"


class TestTemplateSchemaProviderMemory:
    def test_throws_the_first_validation_error_for_an_invalid_template_and_does_not_register_it(self):
        provider = TemplateSchemaProviderMemory()
        with pytest.raises(ValidationException):
            provider.add_template(INVALID_TEMPLATE)
        assert provider.get_all_schemas() == []

    def test_still_registers_a_valid_template(self):
        provider = TemplateSchemaProviderMemory()
        provider.add_template(VALID_TEMPLATE)
        assert len(provider.get_all_schemas()) == 1
        assert provider.get_schema("com.example.demo") is not None

    def test_rejects_a_block_line_inside_structure(self):
        with pytest.raises(ValidationException) as info:
            TemplateSchemaProviderMemory().add_template(
                "Template (@stxt.template): com.example.demo\n\tStructure >>\n\t\tRoot >>\n")
        assert info.value.code == "INVALID_CHILD_LINE"


class TestSchemaProviderContract:
    def test_schema_provider_meta_returns_none_for_any_namespace_other_than_stxt_schema(self):
        meta = SchemaProviderMeta()
        assert meta.get_schema("com.example.unknown") is None
        assert meta.get_schema("@stxt.template") is None
        assert meta.get_schema("@stxt.schema") is not None

    def test_meta_template_provider_returns_none_for_any_namespace_other_than_stxt_template(self):
        meta = MetaTemplateSchemaProvider()
        assert meta.get_schema("com.example.unknown") is None
        assert meta.get_schema("@stxt.schema") is None
        assert meta.get_schema("@stxt.template") is not None

    def test_schema_provider_memory_with_the_default_meta_parent_returns_none_for_an_unknown_namespace(self):
        assert SchemaProviderMemory().get_schema("com.example.unknown") is None
        assert TemplateSchemaProviderMemory().get_schema("com.example.unknown") is None
        assert UnifiedSchemaProvider().get_schema("com.example.unknown") is None

    def test_schema_validator_reports_schema_not_found_as_a_finding_without_throwing(self):
        validator = SchemaValidator(SchemaProviderMemory(), True)
        doc = Parser().parse("Doc (com.example.unknown): x\n")[0]
        errors = validator.validate(doc)
        assert [e.code for e in errors] == ["SCHEMA_NOT_FOUND"]

    def test_the_meta_schema_validates_itself(self):
        meta = SchemaProviderMeta()
        doc = Parser().parse(SchemaProviderMeta.META_TEXT)[0]
        assert SchemaValidator(meta, True).validate(doc) == []
        template = Parser().parse(MetaTemplateSchemaProvider.META_TEXT)[0]
        assert SchemaValidator(MetaTemplateSchemaProvider(), True).validate(template) == []


class TestUnifiedSchemaProvider:
    def test_loads_schemas_and_templates_and_serves_the_meta_schemas(self):
        provider = UnifiedSchemaProvider()
        provider.add_file(VALID_SCHEMA)
        provider.add_file(VALID_TEMPLATE.replace("com.example.demo", "com.example.other"))
        provider.add_file("Other (com.example.ignored): x\n")
        assert sorted(s.get_namespace() for s in provider.get_all_schemas()) == ["com.example.demo", "com.example.other"]
        assert provider.get_schema("@stxt.schema") is not None
        assert provider.get_schema("@stxt.template") is not None
        provider.clear()
        assert provider.get_all_schemas() == []

    def test_an_invalid_definition_is_not_loaded(self):
        provider = UnifiedSchemaProvider()
        with pytest.raises(ValidationException):
            provider.add_file(INVALID_SCHEMA)
        with pytest.raises(ValidationException):
            provider.add_file(INVALID_TEMPLATE)
        assert provider.get_all_schemas() == []
