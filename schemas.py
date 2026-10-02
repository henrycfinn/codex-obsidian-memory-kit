"""Hermes tool schemas. These descriptions are intentionally agent-readable."""

LIBRARIAN_CHANGE = {
    "name": "librarian_change",
    "description": (
        "Create, update, or delete governed text knowledge files as one trust-aware transaction. "
        "Use this INSTEAD OF write_file or patch for files inside the configured knowledge root, including Hermes llm-wiki pages. "
        "Safe additive changes auto-apply; destructive, conflicting, low-confidence, human-controlled, raw-source mutations, major rewrites, "
        "and oversized batches are staged as review proposals without changing canonical knowledge. Supports plain Markdown folders, Obsidian vaults, and optional QMD/Git integrations."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Short transaction summary, e.g. 'Ingest paper on retrieval caching'.",
            },
            "changes": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path relative to the knowledge root, or an absolute path inside it.",
                        },
                        "action": {
                            "type": "string",
                            "enum": ["write", "delete"],
                            "description": "write creates/replaces a text file; delete removes it after review.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Complete desired text for write actions. Omit for delete.",
                        },
                        "risk_flags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Escalation hints such as conflict, contradiction, decision, policy, uncertain, low_confidence, archive, merge, split, rename. Flags can escalate but never bypass deterministic checks.",
                        },
                    },
                    "required": ["path", "action"],
                },
            },
            "risk_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Transaction-wide escalation flags. Use when the source conflicts with known knowledge or the change affects an important decision/policy.",
            },
            "dry_run": {
                "type": "boolean",
                "description": "When true, classify and show diffs without writing or staging a proposal.",
            },
        },
        "required": ["changes"],
    },
}

LIBRARIAN_STATUS = {
    "name": "librarian_status",
    "description": "Inspect Agentic Librarian health: configured knowledge root, Obsidian detection, pending review count, QMD availability/sync mode, Git checkpoint state, and runtime-data location.",
    "parameters": {"type": "object", "properties": {}},
}

LIBRARIAN_REVIEW_QUEUE = {
    "name": "librarian_review_queue",
    "description": "List staged knowledge changes that need human review. Returns summaries, reasons, paths, and proposal IDs without dumping full proposed content.",
    "parameters": {
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
    },
}

LIBRARIAN_GET_PROPOSAL = {
    "name": "librarian_get_proposal",
    "description": "Read one staged proposal, including deterministic reasons and unified diffs. By default omits full replacement content to keep review concise.",
    "parameters": {
        "type": "object",
        "properties": {
            "proposal_id": {"type": "string"},
            "include_content": {"type": "boolean"},
        },
        "required": ["proposal_id"],
    },
}

LIBRARIAN_APPLY_PROPOSAL = {
    "name": "librarian_apply_proposal",
    "description": (
        "Apply the exact contents of a staged proposal after human approval. This tool is always escalated to Hermes' approval gate. "
        "Before applying, it re-hashes every target and refuses stale proposals if canonical knowledge changed after staging."
    ),
    "parameters": {
        "type": "object",
        "properties": {"proposal_id": {"type": "string"}},
        "required": ["proposal_id"],
    },
}

LIBRARIAN_REJECT_PROPOSAL = {
    "name": "librarian_reject_proposal",
    "description": "Reject a staged proposal without changing canonical knowledge. The rejected proposal is retained locally for audit history.",
    "parameters": {
        "type": "object",
        "properties": {
            "proposal_id": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["proposal_id"],
    },
}

LIBRARIAN_HISTORY = {
    "name": "librarian_history",
    "description": "Show recent applied transaction receipts (paths, hashes, decision mode, optional QMD/Git results) without storing or returning note contents.",
    "parameters": {
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
    },
}

LIBRARIAN_CONFIGURE = {
    "name": "librarian_configure",
    "description": (
        "Configure Agentic Librarian settings such as the knowledge root, autonomy policy, QMD post-write synchronization, and Git checkpoints. "
        "Changing configuration requires human approval. Use librarian_status first when unsure."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "knowledge_root": {"type": "string", "description": "Existing directory containing canonical knowledge."},
            "policy_mode": {"type": "string", "enum": ["strict", "balanced", "autonomous"]},
            "qmd_sync": {"type": "string", "enum": ["off", "update", "update_and_embed"]},
            "git_checkpoint": {"type": "boolean"},
            "enforce_direct_writes": {"type": "boolean"},
        },
    },
}


LIBRARIAN_DOCTOR = {
    "name": "librarian_doctor",
    "description": "Run deterministic deployment diagnostics and return machine-readable checks for root access, plugin data, policy, pending proposals, QMD, and Git.",
    "parameters": {"type": "object", "properties": {}},
}
ALL_SCHEMAS = [
    LIBRARIAN_CHANGE,
    LIBRARIAN_STATUS,
    LIBRARIAN_DOCTOR,
    LIBRARIAN_REVIEW_QUEUE,
    LIBRARIAN_GET_PROPOSAL,
    LIBRARIAN_APPLY_PROPOSAL,
    LIBRARIAN_REJECT_PROPOSAL,
    LIBRARIAN_HISTORY,
    LIBRARIAN_CONFIGURE,
]
