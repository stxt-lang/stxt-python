"""STXT exceptions.

Every exception carries an UPPERCASE error code that is identical across
implementations: error codes are part of the conformance surface
(``stxt-impl/exceptions/exceptions.txt``).
"""

from __future__ import annotations


class ParseException(Exception):
    """Syntax error detected while parsing (lexical/structural phase, not schema).

    Attributes:
        line: line number of the document where the error was detected.
        code: error code in UPPERCASE (e.g. ``INVALID_LINE``).
        message: human-readable description.
    """

    def __init__(self, line: int, code: str, message: str) -> None:
        super().__init__(message)
        self.line = line
        self.code = code
        self.message = message

    def get_line(self) -> int:
        """Line number of the document where the error was detected."""
        return self.line

    def get_code(self) -> str:
        """Error code, in UPPERCASE."""
        return self.code

    def get_message(self) -> str:
        """Human-readable description of the error."""
        return self.message

    def with_line(self, new_line: int) -> "ParseException":
        """A copy of this exception, preserving its concrete subtype, located at another line.

        Used to shift the errors of re-parsed blocks to the line of the original document
        (see the template parser).
        """
        return type(self)(new_line, self.code, self.message)

    def __str__(self) -> str:
        return f"[{self.code}] line {self.line}: {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.line!r}, {self.code!r}, {self.message!r})"


class ValidationException(ParseException):
    """Semantic validation error (schema, type or cardinality), detected when a node is closed.

    It extends :class:`ParseException` so both travel together in ``ParseResult.get_errors()``;
    code that tells them apart (e.g. an editor painting validation errors as warnings) must
    preserve the subtype.
    """


class RuntimeException(Exception):
    """Error that is not tied to a line of the document.

    A wrong use of the API or an inconsistency found at runtime (an ambiguous child, a type
    registered twice, a node attached twice...).

    Attributes:
        code: error code in UPPERCASE (e.g. ``AMBIGUOUS_CHILD``).
        message: human-readable description.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def get_code(self) -> str:
        """Error code, in UPPERCASE."""
        return self.code

    def get_message(self) -> str:
        """Human-readable description of the error."""
        return self.message

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.code!r}, {self.message!r})"


__all__ = ["ParseException", "ValidationException", "RuntimeException"]
