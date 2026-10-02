---
name: librarian
version: 1.1.0
description: "Trust-aware autonomous governance for Markdown knowledge bases; works with Hermes llm-wiki, Obsidian, QMD, and plain folders."
author: Community
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [wiki, knowledge-base, governance, obsidian, qmd, llm-wiki, hitl]
    category: research
    related_skills: [llm-wiki, obsidian]
---

# Agentic Librarian

Agentic Librarian is a governance layer for a Markdown knowledge base. It does not replace the knowledge system. It lets an agent work autonomously on routine, source-backed changes while staging risky changes for human review.

## Core rule

**Use `librarian_change` for governed knowledge writes.** Do not bypass it with `write_file`, `patch`, or shell commands inside the configured knowledge root.

The plugin classifies changes deterministically and rechecks base hashes immediately before writing:

- routine new pages and small/additive updates can auto-apply;
- deletion, raw-source mutation, large rewrites, human-controlled files, conflicts, contradictions, low-confidence claims, and other explicitly risky changes are staged;
- staged proposals do not change canonical knowledge;
- applying a proposal re-checks the target hashes and refuses stale proposals.

## Reference memory architecture

When the user combines Hermes, an Obsidian vault, QMD, and this plugin, follow the four-layer contract documented in `docs/memory-architecture.md`: Obsidian/Markdown is canonical, QMD is retrieval-only, the Librarian governs writes, and Hermes performs reasoning/orchestration. Never treat QMD snippets or pending proposals as canonical memory.

## Works with several setups

### Plain Markdown folder

No optional dependency is required. The configured folder is canonical knowledge. Filename similarity provides a lightweight duplicate check.

### Obsidian

An Obsidian vault is still just the canonical Markdown folder. `.obsidian/` is excluded from governance by default. Preserve the user's existing folder structure; do not force an `entities/`, `concepts/`, or other taxonomy unless their existing wiki already uses it.

### Hermes `llm-wiki`

Use the built-in `llm-wiki` skill for research, synthesis, cross-linking, provenance, and wiki conventions. Route its canonical writes through `librarian_change` instead of direct `write_file`/`patch` calls.

The Librarian is a wrapper/governor, not a fork of `llm-wiki`.

### QMD

When QMD is installed, treat it as retrieval/index infrastructure, never as the source of truth.

Before creating a note:

1. Search QMD or use the Librarian's duplicate preflight.
2. Use QMD results as locators.
3. Read the underlying Markdown file before relying on a claim.
4. Write only through `librarian_change`.

QMD post-write synchronization is **off by default**. It can be configured to run `qmd update` or `qmd update` plus `qmd embed` after a successful transaction. Do not enable this automatically: QMD collections may have user-defined update behavior.

### Git

Git checkpoints are optional. If enabled, the plugin commits a successfully applied transaction only when the repository was clean before the transaction. Git is a recovery/audit layer, not a requirement.

## Session workflow

### 1. Check status when setup is uncertain

Call:

`librarian_status`

Confirm:

- the canonical knowledge root;
- policy mode;
- pending proposal count;
- whether Obsidian, QMD, and Git are detected;
- whether direct-write enforcement is active.

If no knowledge root is found, ask the user which existing folder should be canonical, then use `librarian_configure`. Configuration changes require human approval.

### 2. Orient before changing an existing wiki

Respect the wiki's own structure and instructions. If the repository contains files such as `SCHEMA.md`, `index.md`, `log.md`, `AGENTS.md`, or project-specific instructions, read the relevant files before proposing changes.

For Hermes `llm-wiki`, follow its orientation workflow. For an arbitrary Obsidian vault, inspect the relevant topic area rather than assuming an `llm-wiki` layout.

### 3. Search before write

For a new page or substantial update, look for existing related material first. Prefer QMD when available and already configured; otherwise use Hermes file search and the plugin's filename duplicate check.

Avoid:

- duplicate topic pages;
- parallel spellings of the same entity;
- silently replacing an established claim;
- promoting a pending proposal into evidence.

Runtime proposals are intentionally stored outside the knowledge root and should not be copied into the vault.

### 4. Submit one coherent transaction

Use `librarian_change` with a concise summary and all related file changes together.

Example structure:

```json
{
  "summary": "Integrate new retrieval research",
  "changes": [
    {"path": "Research/retrieval.md", "action": "write", "content": "<complete desired file>"},
    {"path": "Index.md", "action": "write", "content": "<complete desired file>"}
  ]
}
```

Provide the **complete desired content** for each `write`. The plugin computes the diff itself.

### 5. Escalate known uncertainty

Use `risk_flags` when semantic judgment says the change is risky. Common flags:

- `conflict`
- `contradiction`
- `destructive`
- `decision`
- `policy`
- `schema`
- `uncertain`
- `low_confidence`
- `archive`
- `merge`
- `split`
- `rename`

Risk flags can only escalate. They never turn a deterministic review decision into an automatic one.

### 6. Handle the result

Possible results include:

- `auto_applied`: canonical files changed and a receipt was recorded;
- `review_required`: canonical files were not changed; a durable proposal ID and compact `review_card` were created;
- `dry_run`: classification/diffs only;
- an error or block: fix the input rather than bypassing governance.

When a proposal is staged during the active task, immediately present the `review_card` to the user. It is the review-ready alert: make a compact table the primary review surface with **Article** (render per-file `review_page` as the clickable proposed-vs-current diff), **What changes** (use `change_summary`, add/remove counts, and the reason for review), and an optional **Current article** link (render the preview-safe `current_page`, not `markdown_path`). The overall `review_page` remains a color-coded all-files diff: green additions, red deletions, and black unchanged context. Use readable article titles as link labels, never opaque generated filenames. Show visible before/after content inline only for deletions or when requested; never ask a user to approve a deletion without showing what would be deleted. Use the card's short natural-language approve/reject replies rather than making the user repeat a proposal ID. Where the host supports native approval buttons, route final application through that gate; otherwise retain the short text fallback. Do not expect the user to discover a queue or a separate notification center. Routine low-risk changes remain autonomous, so this only occurs when a review gate is already required.

### 7. Review only when useful

Use `librarian_review_queue` to list pending items. Use `librarian_get_proposal` for its review card, diff, and reasons. Start with the compact card; provide full unified diffs or full proposed content only for the files the user asks to inspect.

`librarian_apply_proposal` uses Hermes' native approval gate and then performs a stale-base check. If a target changed after proposal creation, the proposal is moved to stale and is not applied.

Use `librarian_reject_proposal` to retain a rejected item in local audit history without modifying knowledge.

## Autonomy modes

### `balanced` (default)

Recommended for most users. Auto-applies routine additions and bounded updates; reviews substantial removals/rewrites, duplicates, control files, source mutations, and flagged semantic risks.

### `strict`

Also stages non-additive updates to existing files. Appropriate for highly controlled knowledge bases.

### `autonomous`

Allows more routine changes, including creation despite a likely duplicate candidate, but still does not auto-delete or bypass protected-path/raw-source safeguards.

## Important trust boundaries

The plugin governs Hermes file-tool writes and provides a conservative guard for obvious shell mutations. It is **not an operating-system sandbox**. External applications, editors, scripts, sync clients, and arbitrary shell commands can still modify the knowledge folder with the current user's filesystem permissions.

The strongest workflow is:

1. agents voluntarily use `librarian_change`;
2. direct Hermes `write_file`/`patch` attempts on unambiguously resolved governed paths are blocked;
3. risky changes are staged;
4. proposal application verifies current hashes;
5. optional Git provides rollback/audit.

## Privacy

Agentic Librarian is local-first and has no telemetry. Proposal bodies are stored locally under Hermes plugin data, outside the knowledge root. Receipts contain hashes/paths and transaction metadata but not note bodies.
