# Security & Trust Model

Agentic Librarian is a **knowledge-integrity guardrail**, not a security sandbox.

Understanding that distinction is important.

## Assets

The plugin tries to protect:

- canonical Markdown knowledge;
- human-authored control/schema instructions;
- immutable source captures;
- the integrity of reviewed proposals;
- the ability to audit what an autonomous agent changed.

## Threats addressed

### Accidental destructive agent edits

Deletes and sufficiently destructive rewrites are staged rather than silently applied.

### Silent source mutation

Existing files in configured raw/source paths require review.

### Agent bypass through ordinary Hermes file tools

`pre_tool_call` blocks `write_file` and `patch` when they unambiguously target governed files under the canonical root, directing the model to `librarian_change`.

### Review applied to the wrong base version

Every proposal stores current target hashes. Immediately before applying a reviewed proposal, all hashes are rechecked. A mismatch marks the proposal stale and prevents application.

### Concurrent Librarian transactions and partial multi-file writes

Librarian processes on the same machine coordinate with a root-keyed lock, then recheck base hashes immediately before mutation. A stale base is refused. The service also snapshots current local text and attempts rollback when a write fails after earlier transaction members have changed.

### Retrieval contamination from pending proposals

Proposal bodies live outside the knowledge root.

### Accidental Git capture of unrelated work

Git checkpoints require a clean repository before the transaction and stage only transaction paths.

## Threats NOT fully addressed

### Arbitrary shell/process filesystem mutation

A process running as the user can write the same files the user can write. The plugin's terminal hook catches only obvious commands that name the canonical root and contain common mutation markers. It is not a shell parser or OS access-control system.

Do not claim that enabling `guard_terminal_writes` makes bypass impossible.

For a stronger boundary, use operating-system permissions, a dedicated account/worktree, filesystem snapshots, or another sandbox appropriate to the environment.

### External editors, other hosts, and sync tools

Obsidian, Git clients, cloud-sync software, IDEs, agents that bypass the Librarian, user scripts, and writers on another host operate outside the local lock. Stale-proposal checks protect against applying an old proposal after such a change, but the plugin cannot stop those external writes.

### Semantic truth

Deterministic checks can verify paths, diffs, hashes, and declared provenance structures. They cannot prove that an LLM interpreted a source correctly.

Agent-provided flags such as `conflict` and `low_confidence` help escalate semantic uncertainty, but a model can fail to notice an error. Human review, multiple sources, and optional independent verification remain valuable for consequential knowledge.

### Malicious installed plugin code

Hermes native plugins execute in the Hermes process with user permissions. Only install plugin code you trust and review changes before upgrading.

## Local data

Agentic Librarian itself sends no telemetry and starts no network listener.

It can invoke optional local binaries:

- `qmd` for local search/index maintenance;
- `git` for local repository commits.

The plugin does not run `git push`, alter remotes, or make network requests.

## Proposal confidentiality

Pending proposal JSON contains the exact proposed note content. It is stored locally under the Hermes profile's plugin-data directory because exact application requires durable content.

Treat that directory with the same confidentiality as the knowledge base itself. Receipts intentionally do not contain note bodies.

## Path handling

All governed paths are resolved under `knowledge_root`. Traversal and resolved symlink escapes are refused. Excluded metadata paths remain outside governance.

## Public repository hygiene

The source repository includes `scripts/check_public_repo.py`, which looks for common credential formats, private keys, absolute user-home paths, runtime state, and other accidental private material.

This is defense-in-depth, not a complete secret scanner. Run a dedicated secret scanner as well if your release process already uses one.

## Reporting a vulnerability

See the root `SECURITY.md` for responsible reporting guidance.
