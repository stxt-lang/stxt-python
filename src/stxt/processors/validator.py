"""Validator: process hook invoked by the parser when each node is closed
(``stxt-impl/processors/validator.txt``)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.node import Node
from ..exceptions import ValidationException


class Validator(ABC):
    """Validates nodes in streaming. Register it with :meth:`Parser.register_validator`."""

    @abstractmethod
    def validate(self, node: Node) -> list[ValidationException]:
        """Validates an already closed node and RETURNS every error found (without raising),
        letting the caller collect errors from several nodes. An empty list means valid."""
