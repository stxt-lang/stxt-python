"""Language constants (STXT-SPEC sections 3, 5, 6, 8 and 9)."""

COMMENT_CHAR = "#"
TAB_SPACES = 4
TAB = "\t"
SPACE = " "
SEP_NODE = ":"
SEP_TEXT_NODE = ">>"
DEFAULT_ENCODING = "UTF-8"
EMPTY_NAMESPACE = ""

# Version of STXT-SPEC (the base syntax) this library implements; "STXT 1.0" on its own means
# this number (STXT-SPEC §1.1). Each specification is versioned independently. It is distinct
# from the package version (``stxt.__version__``), which follows the releases of the port.
SPEC_VERSION = "1.0"
