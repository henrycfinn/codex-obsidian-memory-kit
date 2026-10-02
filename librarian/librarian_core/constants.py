"""Shared constants for Agentic Librarian."""

PLUGIN_ID = "agentic-librarian"
PLUGIN_VERSION = "1.1.0"
TOOLSET = "agentic_librarian"

RISK_FLAGS_REVIEW = {
    "conflict",
    "contradiction",
    "destructive",
    "decision",
    "policy",
    "schema",
    "uncertain",
    "low_confidence",
    "archive",
    "merge",
    "split",
    "rename",
}

TERMINAL_MUTATION_MARKERS = (
    ">",
    ">>",
    " tee ",
    "rm ",
    "mv ",
    "cp ",
    "sed -i",
    "perl -pi",
    "truncate ",
    "touch ",
    "write_text(",
    "write_bytes(",
)
