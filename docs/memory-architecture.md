# Hermes Memory Architecture

This guide describes a durable local-first memory pattern for Hermes users who combine an Obsidian vault, QMD, and Agentic Librarian.

The key design decision is to give each layer one clear responsibility:

```text
                         Hermes Agent
                  reasoning, research, planning
                              │
                 llm-wiki / other knowledge skills
                              │
                 search → synthesize → propose changes
                              │
                    Agentic Librarian
              policy, diffs, review, stale checks, receipts
                              │
                 approved coherent file transaction
                              ▼
                   Obsidian Markdown vault
                  canonical, human-readable memory
                              │
                     QMD collection/index
             retrieval, ranking, duplicate discovery
```

## The four-layer contract

### 1. Obsidian/Markdown is canonical memory

The vault is the source of truth. It contains the notes, links, indexes, decisions, source summaries, and operating instructions that humans should be able to inspect and edit directly.

Obsidian is useful here because it provides a durable human interface, backlinks, graph navigation, and a folder/file format that remains usable without Obsidian. The architecture does not require a particular folder taxonomy. Existing vault conventions win.

### 2. QMD is retrieval infrastructure

QMD is an index and retrieval engine over the canonical files. It helps Hermes locate relevant notes, compare nearby topics, and detect likely duplicates.

QMD is not authoritative. A search result, chunk, embedding, or ranking is a locator—not the final fact. For consequential work, Hermes should open the underlying Markdown note and reason from the canonical file.

Keep QMD collections scoped to the intended vault or knowledge root. Exclude Hermes runtime/plugin data so pending proposals are not retrieved as established knowledge.

### 3. Agentic Librarian is the write-governance boundary

The Librarian sits between Hermes knowledge work and canonical file mutation. It turns a proposed set of file changes into one deterministic transaction:

1. resolve paths inside the configured root;
2. read current canonical files;
3. calculate diffs, hashes, duplicate signals, and risk reasons;
4. auto-apply routine changes or stage risky changes;
5. re-check base hashes immediately before writing;
6. preserve file characteristics during atomic replacement;
7. record a local receipt;
8. optionally refresh QMD and create a Git checkpoint.

This makes autonomy selective rather than all-or-nothing. Hermes can maintain ordinary memory without asking for approval on every edit, while deletes, contradictions, policy changes, major rewrites, and uncertain changes remain reviewable.

### 4. Hermes is the reasoning and orchestration layer

Hermes decides what to research, what to synthesize, which notes are relevant, and what knowledge change would be useful. Its `llm-wiki` workflow remains responsible for knowledge organization and provenance conventions.

The Librarian is not a replacement wiki and does not become a second memory database. It governs the mutation of the existing Markdown memory system.

## Recommended ingestion loop

For a research or conversation event:

```text
1. Hermes identifies the topic and source material.
2. QMD/Hermes search locates related canonical notes.
3. Hermes reads the relevant Markdown notes, not only snippets.
4. Hermes synthesizes a proposed update with provenance.
5. Hermes batches related changes into one librarian_change transaction.
6. Librarian classifies the transaction.
7. Routine changes apply; risky changes become proposals.
8. QMD is refreshed after the transaction when explicitly enabled.
9. Git optionally checkpoints the applied files.
```

Batching matters. One coherent transaction produces one diff, one risk decision, one receipt, and—when enabled—one post-write QMD refresh. It avoids partial updates where an index points to a note that was not written or a backlink is updated without its target.

## Recommended defaults

```yaml
policy_mode: balanced
qmd_duplicate_check: true
qmd_sync: off
git_checkpoint: false
enforce_direct_writes: true
guard_terminal_writes: true
```

Start with QMD synchronization off. Confirm the QMD collection and update behavior first, then enable `update` if desired. Treat embedding as a deliberate performance and freshness decision rather than an invisible side effect of every note edit.

Use Git checkpoints when the vault is already a clean repository and the user wants transaction-level recovery. Git is optional and does not replace the Librarian's stale checks.

## What agents must and must not do

Agents should:

- search before creating a new note;
- treat QMD results as locators;
- read canonical notes before making consequential claims;
- use `librarian_change` for governed writes;
- batch related note/index/backlink changes together;
- include provenance and risk flags when uncertainty is meaningful;
- surface review proposals when they block an important workflow.

Agents should not:

- write directly into the vault with `write_file`, `patch`, or shell commands when the Librarian governs that path;
- treat an embedding or search chunk as authoritative memory;
- copy pending proposal bodies into the vault;
- silently reorganize an established Obsidian vault;
- enable QMD embedding or alter QMD configuration without explicit user intent;
- assume that shell guarding is an operating-system sandbox.

## Why this architecture scales

The layers can evolve independently:

- Obsidian can be replaced by another Markdown editor without changing policy logic.
- QMD can be replaced by another retrieval adapter without changing canonical storage.
- Hermes skills and models can improve without receiving unrestricted write authority.
- The Librarian can add stricter policy, semantic review, or recovery features without becoming the memory store.

The durable invariant is simple: human-readable Markdown remains canonical, retrieval remains advisory, reasoning remains in Hermes, and all autonomous mutation passes through an inspectable policy boundary.