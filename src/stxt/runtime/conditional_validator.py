"""ConditionalValidator: only validates namespaced nodes (a consumer convenience, not normative)."""

from __future__ import annotations

from ..core.node import Node
from ..exceptions import ValidationException
from ..processors.validator import Validator
from ..schema.schema_validator import SchemaValidator


class ConditionalValidator(Validator):
    """Wrapper around a :class:`SchemaValidator` that only validates namespaced nodes, so that a
    document mixing schema-bound and free nodes does not report the free ones as unknown.

    .. deprecated:: 0.8.0
        :class:`SchemaValidator` applies this rule itself (STXT-SCHEMA-SPEC 5, the empty
        namespace is never validated), so the wrapper adds nothing. Register the
        ``SchemaValidator`` directly. Kept for compatibility; to be removed in 1.0.
    """

    def __init__(self, schema_validator: SchemaValidator) -> None:
        self._schema_validator = schema_validator

    def validate(self, node: Node) -> list[ValidationException]:
        if node.get_namespace() != "":
            return self._schema_validator.validate(node)
        return []


__all__ = ["ConditionalValidator"]
