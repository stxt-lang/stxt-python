"""Language constants (STXT-SPEC sections 3, 5, 6, 8 and 9)."""

COMMENT_CHAR = "#"
TAB_SPACES = 4
TAB = "\t"
SPACE = " "
SEP_NODE = ":"
SEP_TEXT_NODE = ">>"
DEFAULT_ENCODING = "UTF-8"
EMPTY_NAMESPACE = ""

# Parser limits (STXT-SPEC 11.2). Defaults of a conforming parser; configure them per parser
# with the ``max_*`` keyword arguments of ``Parser``, and -1 disables the corresponding limit.
DEFAULT_MAX_NESTING = 100
DEFAULT_MAX_LINE_LENGTH = 10000
DEFAULT_MAX_INPUT_SIZE = 10000000

# Upper bound of Min/Max in a schema and of the numbers of a template cardinality: 2^32 - 1
# (STXT-SCHEMA-SPEC 10, STXT-TEMPLATE-SPEC 7.1). A greater value is CARDINALITY_NOT_VALID;
# "no maximum" is said by omitting Max.
MAX_CARDINALITY = 4294967295
# Digits of MAX_CARDINALITY: a longer numeral exceeds the bound before it is converted, which
# keeps ``int()`` (limited to 4 300 digits by CPython) out of reach of a definition.
MAX_CARDINALITY_DIGITS = 10

# Date of the STXT-SPEC text (the base syntax) this library implements, YYYY-MM-DD. The
# specifications carry no version number: each one has a date and a status (STXT-SPEC §1.1),
# and the date pinned here is the one the conformance kit certifies for STXT-SPEC, not the
# ``Last modif`` of the specification, so an editorial change of the text does not move it. It
# is distinct from the package version (``stxt.__version__``), which follows the releases of
# the port.
SPEC_VERSION = "2026-09-07"
