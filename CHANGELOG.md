# Changelog

All notable changes to the `stxt` Python package. The version number announces the same
language scope as `@stxt-lang/core` and `dev.stxt:stxt-core` of the same number.

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
