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

# Version of STXT-SPEC (the base syntax) this library implements; "STXT 1.0" on its own means
# this number (STXT-SPEC §1.1). Each specification is versioned independently. It is distinct
# from the package version (``stxt.__version__``), which follows the releases of the port.
SPEC_VERSION = "1.0"
