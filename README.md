# stxt

Parser and schema validator for **STXT**, an indentation-based structured-text format, in pure
Python (no dependencies, Python 3.10+).

STXT is a plain-text format for writing structured, semantic documents: no braces, no closing
tags, just indentation. It is designed to be equally readable by humans and by machines, and it
comes with an optional schema layer so documents can be validated.

- Website and language reference: <https://stxt.dev>
- TypeScript implementation: [`@stxt-lang/core`](https://www.npmjs.com/package/@stxt-lang/core) on npm
- Java implementation: [`dev.stxt:stxt-core`](https://central.sonatype.com/artifact/dev.stxt/stxt-core) on Maven Central
- VS Code extension: [STXT - Semantic Text](https://marketplace.visualstudio.com/items?itemName=stxt-lang.stxt)

This package is a port of the language's neutral implementation blueprint (`stxt-impl`), so it
shares its behaviour, its node model and its error codes with the other implementations.

## What STXT looks like

```stxt
# A line starting with '#' is a comment

Article (blog.post):
    Title: Getting started with STXT
    Author: Joan
    Published: 2026-07-28
    Tags:
        Tag: parser
        Tag: text-format
    Body >>
        Everything indented under a '>>' node is kept verbatim
        as a block of text lines.
```

- `Name: value` declares an **inline node**.
- `Name >>` opens a **text block**; every deeper-indented line belongs to it.
- Indentation is **one level per tab or per 4 spaces**.
- `Name (a.b.c):` attaches a **namespace** to a node; children inherit it unless they declare
  their own.

## Install

```bash
pip install stxt
```

## Parsing

```python
from stxt import Parser, InlineNode

text = "Article (blog.post):\n\tTitle: Getting started with STXT\n\tAuthor: Joan\n"

parser = Parser()

# parse_result() collects every error instead of stopping at the first one
result = parser.parse_result(text)

for error in result.get_errors():
    print(f"line {error.line} [{error.code}]: {error.message}")

article = result.get_nodes()[0]

print(article.get_name())        # "Article"
print(article.get_namespace())   # "blog.post"
if isinstance(article, InlineNode):
    print(article.get_child("Title").get_text())   # "Getting started with STXT"
```

Use `parser.parse(text)` instead if you prefer an exception (`ParseException`) on the first
error.

## Working with the tree

`Node` is an abstract class with exactly two forms, and each one owns only what is really its
own: `InlineNode` (`Name: value`) has the optional value, the children and the child lookups
(`get_children()`, `get_child(name)`, `get_children_by_name(name)`); `TextNode` (`Name >>`)
has the literal text lines and nothing else. What they share lives in `Node`: name and
canonical name, declared and effective namespace, source line, parent (always an `InlineNode`)
and `get_text()` — the value of an inline node or the joined lines of a text node. Walking a
tree therefore asks for the form (`isinstance(node, InlineNode)`), the same way the canonical
tree of STXT-TREE-SPEC has `children` only for inline nodes.

Trees are mutable and keep their own integrity: every node knows its parent, `add_child`
links both ends and refuses a node that already has one, and `remove_child` / `detach()` undo
it. Levels are derived from the chain of parents; the source line is only set by the parser.

```python
from stxt import InlineNode, TextNode

email = InlineNode("Email", "com.example.docs", "Weekly report")
email.add_inline_node("From", "ana@example.com")
to = email.add_inline_node("To")
to.add_inline_node("Address", "bob@example.com")
body = email.add_text_node("Body", "Hi Bob,\n\nSee attached.")

body.get_parent() is email      # True
body.get_level()                # 1
to.get_namespace()              # "com.example.docs", inherited
to.get_declared_namespace()     # "" — it declares none

# Reorganise: move "To" to the front
to.detach()
email.add_child(to, 0)

# Edit in place
email.set_namespace("com.example.mail")   # the whole inheriting subtree follows
body.set_text("Hi Bob,\n\nSee the new attachment.")

for child in email.get_children():
    if isinstance(child, InlineNode):
        print(child.get_value(), len(child.get_children()))
    if isinstance(child, TextNode):
        print(child.get_text_lines())
```

Constructors with two strings always take the second one as the *content* (value or text); the
namespace only appears in the three-argument forms (`InlineNode(name, namespace, value)`), and
`value=` / `namespace=` / `text=` are accepted as keywords too. Adding a node that already has
a parent raises `RuntimeException` with code `NODE_ALREADY_ATTACHED`; adding an ancestor,
`NODE_CYCLE`.

## Validating against a schema

Schemas are themselves STXT documents, written in the reserved `@stxt.schema` namespace (or in
the friendlier `@stxt.template` form, which compiles to a schema). `UnifiedSchemaProvider`
loads either kind, validates it against the corresponding meta-schema, and registers it by
namespace.

```python
from stxt import ConditionalValidator, Parser, SchemaValidator, UnifiedSchemaProvider, ValidationException

schema_text = """Schema (@stxt.schema): blog.post
\tNode: Article
\t\tChildren:
\t\t\tChild: Title
\t\t\t\tMin: 1
\t\t\t\tMax: 1
\t\t\tChild: Author
\t\t\t\tMin: 1
\tNode: Title
\tNode: Author
"""

provider = UnifiedSchemaProvider()
provider.add_file(schema_text)

parser = Parser()
# ConditionalValidator only validates nodes that carry a namespace
parser.register_validator(ConditionalValidator(SchemaValidator(provider)))

result = parser.parse_result(document_text)

for error in result.get_errors():
    # Schema problems are ValidationException; syntax problems are plain ParseException
    severity = "warning" if isinstance(error, ValidationException) else "error"
    print(f"{severity} at line {error.line} [{error.code}]: {error.message}")
```

Available value types: `INLINE`, `BLOCK`, `TEXT`, `MARKDOWN`, `BOOLEAN`, `INTEGER`, `NATURAL`,
`NUMBER`, `DATE`, `TIME`, `TIMESTAMP`, `UUID`, `EMAIL`, `URL`, `HEXADECIMAL`, `BINARY`,
`BASE64`, `GROUP`, `ENUM`.

## Finding the schemas: discovery

`UnifiedSchemaProvider` expects you to hand it the schema text. **Discovery** answers the
previous question: *given this document, which schema definitions apply to it?*
`DiscoveryResolver` implements the STXT discovery specification, so a command line, an editor
and a build step all agree on the answer by construction.

Definitions live in `.stxt/` directories. For a given document the resolution chain is,
highest precedence first:

1. every ancestor `.stxt/` directory, nearest first — the ascent does **not** stop at the first
   one, so in a monorepo both the subproject's and the repo root's participate;
2. the user level, `$HOME/.stxt` (`%USERPROFILE%\.stxt` on Windows);
3. the system level, `/etc/stxt` (`%ProgramData%\stxt` on Windows).

Precedence is **per namespace**: the nearest level that defines a namespace wins, and the rest
of the chain still contributes the namespaces that level does not define. Defining one
namespace twice at the same level is a resolution error, and leaves that namespace without an
active definition. When `STXT_PATH` is defined it replaces the whole chain — useful in CI and
tests.

The resolver never touches the file system or the environment itself: you inject a
`DiscoveryFileSystem` and a `DiscoveryEnvironment`. The package ships the two host adapters,
`OsDiscoveryFileSystem` and `SystemDiscoveryEnvironment`, and a `resolve()` shortcut over them;
a test can pass an in-memory tree instead. `DiscoveryResult` implements `SchemaProvider`, so it
goes straight into the validator:

```python
from stxt import ConditionalValidator, Parser, SchemaValidator
from stxt.discovery import resolve

# The chain is per document: pass the directory the document lives in
# (None for stdin or an unsaved buffer, which starts the chain at the user level).
result = resolve("/repo/site/posts")

print(result.get_chain())
# ['/repo/site/.stxt', '/repo/.stxt']   <- both ancestors, nearest first

# Resolution errors are collected, never raised: report them and carry on
for error in result.get_errors():
    print(f"[{error.code}] {error.message}")

parser = Parser()
parser.register_validator(ConditionalValidator(SchemaValidator(result)))
parsed = parser.parse_result(document_text)

definition = result.get_definition("blog.post")
print(definition.file)        # '/repo/site/.stxt/blog.stxt'
print(definition.level_dir)   # '/repo/site/.stxt'  <- the level that won
```

Levels are cached by directory; call `resolver.clear_cache()` on a `DiscoveryResolver` when
the definition files may have changed.

## Observing the parse

`Observer` receives streaming callbacks while the document is parsed — useful for syntax
highlighting, indexes or any per-line bookkeeping. Subclass it and override what you need.

```python
from stxt import Observer, Parser

class LoggingObserver(Observer):
    def on_create(self, node, line_string):
        print("open", node.get_qualified_name())

    def on_finish(self, node):
        print("close", node.get_qualified_name())

parser = Parser()
parser.register_observer(LoggingObserver())
parser.parse_result(text)
```

## Writing STXT back out, and the canonical tree

```python
from stxt import IndentStyle, NodeWriter, to_canonical_json, to_canonical_tree

text = NodeWriter.to_stxt(node, IndentStyle.TABS)                     # a single node
doc = NodeWriter.to_stxt_docs(result.get_nodes(), IndentStyle.SPACES_4)  # a whole document

tree = to_canonical_tree(result.get_nodes())   # the STXT-TREE-SPEC data model (list of dicts)
json_text = to_canonical_json(result.get_nodes())
```

## API surface

Everything importable from `stxt`:

- **Parsing** — `Parser`, `ParseResult`, `Node`, `InlineNode`, `TextNode`, `NO_LINE`,
  `LineIndent`, `parse_line`
- **Exceptions** — `ParseException`, `ValidationException`, `RuntimeException`. Their `message`
  is only the description; `str(e)` adds the frame: `[CODE] line N: message` (or
  `[CODE] message` for `RuntimeException`)
- **Versions** — `__version__` (the package) and `SPEC_VERSION` (the specifications it implements)
- **Extension points** — `Observer`, `Validator`
- **Schemas** — `Schema`, `SchemaValidator`, `SchemaProvider`, `SchemaProviderMemory`,
  `SchemaProviderMeta`, `NodeDefinition`, `ChildDefinition`, `transform_node_to_schema`
- **Templates** — `TemplateSchemaProviderMemory`, `MetaTemplateSchemaProvider`,
  `transform_template_node_to_schema`
- **Runtime** — `UnifiedSchemaProvider`, `ConditionalValidator`, `NodeWriter`, `IndentStyle`,
  `to_canonical_tree`, `to_canonical_json`
- **Discovery** — `DiscoveryResolver`, `DiscoveryResult`, `DiscoveryDefinition`,
  `DiscoveryLevel`, `DiscoveryError`, `DiscoveryFileSystem`, `DiscoveryEntry`,
  `DiscoveryEnvironment`, `OsDiscoveryFileSystem`, `SystemDiscoveryEnvironment` (and
  `stxt.discovery.resolve`)

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
pytest
```

The tests are regression tests against the real corpus of the sibling repository
[`stxt-web`](https://github.com/stxt-lang/stxt-web) (the language specifications and their
examples). The corpus is mandatory: clone `stxt-web` next to this repository, or point at it
with `STXT_WEB=/path/to/stxt-web`; without it the corpus suites fail, they are never skipped.

## License

MIT — see [LICENSE](LICENSE).
