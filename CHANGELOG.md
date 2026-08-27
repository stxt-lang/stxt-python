# Changelog

All notable changes to the `stxt` Python package. The version number announces the same
language scope as `@stxt-lang/core` and `dev.stxt:stxt-core` of the same number.

## 0.14.1 - 2026-08-26

Same number and scope as `@stxt-lang/core` and `dev.stxt:stxt-core` 0.14.1.

### Added

- `Formatter.format(text, style, *, max_nesting=..., max_line_length=..., max_input_size=...)`:
  keyword arguments that configure the limits of the internal parser (STXT-SPEC §11.2; -1
  disables one). Left out, the recommended defaults apply. A limit exceeded shows up in the
  errors like any other syntax error, and the lines the aborted parse never described are
  converted as "other lines" (indentation units only). Needed by tools that expose
  configurable limits and also reformat, like the CLI and the VS Code extension.

## 0.14.0 - 2026-08-26

Same number and scope as `@stxt-lang/core` and `dev.stxt:stxt-core` 0.14.0: the parser limits
of STXT-SPEC §11.2 in the three ports, plus the streaming API.

### Added

- Parser limits (STXT-SPEC §11.2): the parser aborts on inputs that exceed its nesting depth
  (default 100 levels), line length (default 10 000 characters) or total input size (default
  10 000 000 characters). Each limit is configurable per parser (keyword arguments
  `max_nesting`, `max_line_length`, `max_input_size`; -1 disables one) and its error is a
  `LimitException` (codes `LIMIT_NESTING_EXCEEDED`, `LIMIT_LINE_LENGTH_EXCEEDED`,
  `LIMIT_INPUT_SIZE_EXCEEDED`), in every case the last one emitted: after it, no further input
  is processed and the nodes still open are not closed.
- `StreamObserver` (`stxt.processors`, exported from `stxt`), registered with
  `Parser.register_stream_observer`: notified with each completed root node (`on_root_node`)
  and every error (`on_error`), in every mode.
- `Parser.parse_stream(lines)`: streaming mode. The input is an iterable of lines (a file
  object read lazily, a generator; a trailing line break per item is removed) and nothing is
  retained — no nodes, no errors —; the results reach the program only through the registered
  `StreamObserver`s, so memory holds one root tree at a time. Made for files that do not fit
  in memory.

### Changed

- A document that exceeds a default limit — deeper than 100 levels, a line longer than 10 000
  characters, or more than 10 000 000 characters in total — no longer parses unless the limit
  is raised or disabled. This is the language change of the 0.14.0 cycle (STXT-SPEC §11.2,
  `Last modif: 2026-08-26`).

## 0.13.0 - 2026-08-23

Same number and scope as `@stxt-lang/core` and `dev.stxt:stxt-core` 0.13.0: the writing operations of
STXT-TREE-SPEC §11–12, now normative, in the three ports.

### Added

- `Formatter` and `FormatResult` (`stxt.runtime`, exported from `stxt`): the reformatting of STXT-TREE-SPEC §12, a replica of the
  TypeScript `Formatter` of `@stxt-lang/core` 0.11.1. `Formatter.format(text, style)` returns a
  `FormatResult(text, errors)` dataclass: the document rewritten line by line —node lines in canonical
  form, block lines at the level of the block, comments and blank lines kept with their
  indentation units converted— plus the syntax errors found; CRLF and the final newline are
  kept, an initial BOM is removed.

### Changed

- `NodeWriter` writes the canonical text form of STXT-TREE-SPEC §11 (2026-08-23): the
  namespace is declared only where it changes from the parent's — on a root when not empty, on
  a child when it differs — wherever the source declared it. A child repeating its parent's
  namespace used to come out with it; the tree it re-parses to is the same.

### Fixed

- `BASE64`: the padding, when present, must be exactly the one or two `=` that complete the
  last quartet, as in the TypeScript and Java ports (`stxt-impl` `platform.txt`, point 3):
  `aGVsbG8==` and `aGVsbG8x=` are now rejected; `aGVsbG8=` and `aGVsbG8` are still valid.
- Tests: `test_conformance.py` runs the `validate`, `validate-error`, `definition-error` and
  `discovery` categories of the conformance kit (kit 1.0, 276 cases in all); the in-memory
  discovery adapters moved to `tests/discovery_memory.py`, shared with `test_discovery.py`.

## 0.12.0 - 2026-08-22

Same number and scope as `@stxt-lang/core` and `dev.stxt:stxt-core` 0.12.0: the three ports are level again
(the 0.11.1 of `@stxt-lang/core` was the JS-only `Formatter`).

### Changed

- An indented first line is now a parse error, `INDENTATION_LEVEL_NOT_VALID` (STXT-SPEC §8.3,
  clarified on 2026-08-22): with no open node the reference level is -1, so the first node or
  comment of the document, and the first line after every node has been closed, must be at
  level 0. Until now `\tRoot: x` parsed as a root. As a consequence, a level-1 line after a
  comment closed a root `>>` block is `INDENTATION_LEVEL_NOT_VALID` instead of `INVALID_LINE`.
  Conformance kit cases `parse/indentation-first-line`, `parse/comment-first-line` and
  `parse/comment-closes-root-block-text-after`.
- Tests: `test_conformance.py` runs `stxt-lang/conformance/manifest.json` (the conformance kit,
  `tree` and `parse-error` categories) and replaces `test_tree.py`.

## 0.11.0 - 2026-08-21

The preview of 1.0: everything 1.0 will ship, published first as a 0.x so that the consumers can
move to it and anything left can still be fixed. The public API is the one 1.0 will freeze for
the whole 1.x line. Same scope as `@stxt-lang/core` and `dev.stxt:stxt-core` 0.11.0.

### Removed

- `Node.get_normalized_name()`, deprecated alias of `get_canonical_name()` (it only existed on
  `Node`, never on the schema definitions).
- `ConditionalValidator` (`stxt.runtime.conditional_validator`), deprecated since 0.8.0:
  `SchemaValidator` already lets the nodes without a namespace through (STXT-SCHEMA-SPEC 5),
  so register it directly.

### Added (API parity audit against `@stxt-lang/core` and `dev.stxt:stxt-core`)

- `Type` and `TypeRegistry` are exported from the package root (they were only in
  `stxt.schema`).

### Fixed

- `LineIndent.indent_length` of a text line of a block was the index of the last indentation
  character, one less than the number of characters the indentation took (the comment and node
  cases were right). Fixed in the pseudocode and in the three ports at once, and the field is
  **renamed `content_start`** (the index where the content starts).

### Tests

- `SPEC_VERSION` is compared against the `Metadata/Version` that STXT-SPEC declares in
  `stxt-web/es/stxt-core-ref.stxt`, not only against a literal.

## 0.10.0 - 2026-08-21

### Language changes (STXT-SCHEMA-SPEC 9.5 and 7.2/13, STXT-TEMPLATE-SPEC 14.14)

- Binary types (`HEXADECIMAL`, `BINARY`, `BASE64`): every blank (space U+0020, tab U+0009) is
  removed wherever it is before validating, in both the inline and the block form (the block
  lines are concatenated first). `DE AD BE EF`, `1010 1010` and Base64 wrapped at 76 columns
  validate; `DE:AD`, `DE-AD` and a value that is empty after removing the blanks are
  `INVALID_VALUE`. Before, only the edges of each block line were trimmed.
- An empty `Value:` inside the `Values` of an `ENUM` is a schema error, `VALUE_EMPTY`, at the
  line of that `Value` (condition 14 of STXT-SCHEMA-SPEC 13). In a template, an empty item of
  the `[...]` list (`[a, , b]`, `[a, b,]`) is `VALUE_EMPTY` at the line of the `Structure`
  line; an empty list `[]` stays `VALUES_REQUIRED`.

### Message framing (the same in every port)

- `message` / `get_message()` of `ParseException`, `ValidationException` and
  `RuntimeException` is only the description, with no code and no line; the frame lives in
  `__str__` (`[CODE] line N: message`, `[CODE] message`). This was already the behaviour of
  the Python port; it is now the documented contract, pinned by a test.

### API

- `SPEC_VERSION = "1.0"` (`stxt.SPEC_VERSION`, `stxt.core.constants`): the version of the
  STXT specifications this library implements, distinct from `__version__`.

## 0.9.1 - 2026-08-21

### Error codes renamed (normative annex: STXT-SPEC 11.1, STXT-SCHEMA-SPEC 13.1, STXT-TEMPLATE-SPEC 14.1)

The codes are frozen from 1.0 on; every port uses the same strings. Old -> new:

- Parser: `MIXED_INDENTATION` -> `INDENTATION_MIXED`, `INVALID_NUMBER_SPACES` ->
  `INDENTATION_SPACES_NOT_VALID`, `INLINE_VALUE_NOT_VALID` -> `BLOCK_VALUE_NOT_ALLOWED`,
  `VALIDATION_ERROR` -> `UNEXPECTED_ERROR` (one wrapper code for unforeseen exceptions, in the
  parser and in the schema validator; the exception subtype is kept).
- Document validation: `INVALID_NUMBER` -> `TOO_FEW_CHILDREN` (count < `Min`) and
  `TOO_MANY_CHILDREN` (count > `Max`), `NOT_ALLOWED_TEXT` -> `BLOCK_FORM_NOT_ALLOWED`,
  `NOT_ALLOWED_CHILDREN_TEXT` -> `CHILDREN_NOT_ALLOWED`, `NODE_NOT_EXIST_IN_SCHEMA` ->
  `NODE_NOT_DEFINED_IN_SCHEMA`, `TYPE_NOT_SUPPORTED` -> `TYPE_NOT_VALID`, and a value on a
  `GROUP` node is now `VALUE_NOT_ALLOWED` (`INVALID_VALUE` stays for every other type).
- Schema load: `NOT_STXT_SCHEMA` -> `SCHEMA_ROOT_NOT_VALID` (also raised when the target
  namespace is malformed, previously `INVALID_NAMESPACE`), `INVALID_SCHEMA` ->
  `SCHEMA_NODE_NOT_INLINE` (a schema node written with `>>`), `SCHEMA_MULTIPLE_ROOTS` (a
  document with != 1 root) and `SCHEMA_NAMESPACE_EMPTY` (new check), `NODE_DEF_ALREADY_DEFINED`
  -> `NODE_DUPLICATED`, `CHILD_DEF_ALREADY_DEFINED` -> `CHILD_DUPLICATED`,
  `VALUES_ONLY_SUPPORTED_BY_ENUM` -> `VALUES_NOT_ALLOWED_FOR_TYPE`, `VALUES_EMPTY_FOR_ENUM` ->
  `VALUES_REQUIRED`, `INVALID_INTEGER` -> `CARDINALITY_NOT_VALID`, `DUPLICATED_TYPE` ->
  `TYPE_DUPLICATED`. `INVALID_SIZE_VALUES` -> `VALUES_DUPLICATED`, which is now a
  `ValidationException` with the line of the second `Values` node (was a `RuntimeException`).
- Template load: new `TEMPLATE_ROOT_NOT_VALID` (root not `Template (@stxt.template): ns`, or
  malformed namespace), `TEMPLATE_MULTIPLE_ROOTS` and `TEMPLATE_NAMESPACE_EMPTY` (were
  `INVALID_SCHEMA`), `INVALID_CHILD_LINE` -> `STRUCTURE_LINE_NOT_VALID`, `INVALID_CHILD_COUNT` ->
  `CARDINALITY_NOT_VALID`, `NODE_DEFINED_MULTIPLE_TIMES` -> `REFERENCE_REQUIRED`,
  `NODE_REFERENCE_NOT_VALID` -> `REFERENCE_NAME_NOT_VALID`, `NODE_NOT_FOUND` ->
  `DESCRIPTION_NODE_NOT_FOUND`, `CHILDREN_DESCRIPTION_NOT_ALLOWED` ->
  `DESCRIPTION_CHILDREN_NOT_ALLOWED`, `EXTERNAL_DESCRIPTION_NOT_ALLOWED` ->
  `DESCRIPTION_NOT_ALLOWED_IN_EXTERNAL_NAMESPACE`, `DESCRIPTION_ALREADY_DEFINED` ->
  `DESCRIPTION_DUPLICATED`, `TYPE_DEFINITION_NOT_ALLOWED` ->
  `TYPE_NOT_ALLOWED_IN_EXTERNAL_NAMESPACE`.

### Value types (STXT-SCHEMA-SPEC 9.4)

- `URL` is validated by the grammar of the spec (scheme `://` [userinfo `@`] host [`:` port]
  [`/` path] [`?` query] [`#` fragment]) instead of `urllib`, so every port accepts exactly the
  same values; `core/platform.py` loses `parse_uri`.
- `DATE`, `TIME` and `TIMESTAMP` check the calendar and the clock ranges after the shape
  (new `RangeValue` type, `is_valid_date` / `is_valid_time`): `2026-02-30` and `24:00:00` are
  rejected, including inside a timestamp and its zone offset.
- The fraction of seconds of a `TIMESTAMP` accepts one or more digits (was exactly three).
- `NUMBER` is documented as STXT's own grammar (optional sign, digits with optional fraction,
  optional exponent), not JSON's: `.5`, `5.` and `+1` are valid.

## 0.9.0 - 2026-08-21

### Language change (STXT-SPEC sections 9 and 11)

- The indentation of a comment line (first non-blank character `#`, outside an open `>>`
  block) is now validated exactly like a node's: mixing tabs and spaces on the same line is
  `MIXED_INDENTATION`, a number of spaces that is not a multiple of 4 is
  `INVALID_NUMBER_SPACES`, and a level deeper than the last node's level + 1 is
  `INDENTATION_LEVEL_NOT_VALID`. Same error codes as nodes; no new code.
- A comment still produces no node and never becomes the reference level: only nodes update
  the parser's last level. Blank lines remain exempt. Comments inside block content (deeper
  than the `>>` node) are text as before; a comment at the block's level or shallower still
  closes the block.
- This is the only language change of 0.9.0. Conformance pair:
  `stxt-web/conformance/tree/comment-indent.{stxt,json}`.

## 0.8.1 - 2026-08-21

- *Blank* means only U+0020 and U+0009 (STXT-SPEC section 4) in trimming and name
  normalization.

## 0.8.0 - 2026-08-20

- The three language changes of that day; `ConditionalValidator` deprecated.

## 0.7.1 - 2026-08-17

- The `EMAIL` type also accepts `Name <address>` (STXT-SCHEMA-SPEC 9.4).

## 0.7.0 - 2026-08-16

- First real release: full port of `stxt-impl` (core, tree, schema, template, discovery).
