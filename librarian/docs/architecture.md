# Architecture

## Design target

Agentic Librarian is deliberately smaller than a standalone knowledge-management application. It inserts a governance boundary between an agent's desired knowledge mutation and the existing canonical Markdown folder.

```text
             ┌─────────────────────────┐
             │         Hermes          │
             │ research / llm-wiki /   │
             │ Obsidian-aware workflow │
             └────────────┬────────────┘
                          │
                          ▼
                  librarian_change
                          │
             ┌────────────┴────────────┐
             │ deterministic preflight │
             │ path + diff + policy    │
             └────────────┬────────────┘
                          │
               ┌──────────┴──────────┐
               │                     │
             auto                  review
               │                     │
               ▼                     ▼
        atomic transaction       proposal store
               │                     │
               │               native approval
               │                     │
               │               stale hash check
               │                     │
               └──────────┬──────────┘
                          ▼
                 canonical Markdown
                          │
                 ┌────────┴─────────┐
                 ▼                  ▼
            optional QMD       optional Git
              refresh            commit
```

## Canonical knowledge

`knowledge_root` is the only canonical store controlled by the plugin. It can be:

- a plain Markdown directory;
- a Hermes `llm-wiki` directory;
- an Obsidian vault;
- a subtree or repository that also contains non-governed files.

The plugin does not require a specific taxonomy. Existing `llm-wiki` users can keep the standard `raw/`, `entities/`, `concepts/`, etc. structure; other users keep their own.

## Runtime state

Proposal bodies and receipts are operational state, not knowledge. They live under profile-scoped Hermes plugin data, outside `knowledge_root`.

This avoids a subtle RAG feedback loop:

```text
unapproved proposal -> indexed by retrieval -> retrieved as fact -> reinforced into wiki
```

The separation makes a pending proposal unavailable to normal knowledge indexing unless the user deliberately indexes Hermes' plugin-data directory.

## Transaction state machine

### 1. Prepare

For every requested change:

1. normalize it relative to the configured root;
2. reject path escapes and symlink escapes;
3. reject excluded/non-governed targets;
4. load the current content if it exists;
5. hash the current state;
6. for new Markdown pages, optionally look for duplicate candidates;
7. compute the proposed SHA-256 and unified diff.

### 2. Assess

`librarian_core/policy.py` receives only deterministic inputs and returns:

- `auto`
- `review`
- `block`

Semantic flags from the agent are escalation-only inputs.

At transaction level, any review-required member makes the entire coherent batch a proposal. A batch over `max_auto_changes` is also reviewed.

### 3A. Auto-apply

The service acquires a root-keyed local cross-process lock, rechecks every base hash inside that lock, snapshots current file bodies in memory, writes desired bodies atomically, and rolls back already-mutated members if a later mutation fails. If a base changed after preflight, the transaction returns `retry_required` instead of overwriting it.

The lock coordinates Librarian processes on the same machine. It is not a distributed lock across multiple hosts/network filesystems, so hash checks remain the authoritative optimistic-concurrency guard.

After canonical writes:

- optional Git checkpoint runs if enabled and the repository was clean before the transaction;
- optional QMD sync runs if explicitly enabled;
- a receipt is written.

The optional integrations are post-write audit/index operations. Their failure is surfaced, but the plugin never repeats the knowledge write to compensate.

### 3B. Stage

For review-required transactions:

- canonical files are not touched;
- the exact desired content, base hashes, reasons, and diffs are written into a local proposal;
- the tool returns a proposal ID.

### 4. Apply reviewed proposal

`librarian_apply_proposal` is intercepted by `pre_tool_call` and routed through Hermes' native approval gate.

After approval, the service:

1. loads the pending proposal;
2. verifies it was created for the currently configured knowledge root;
3. hashes every current target again;
4. if any hash differs, moves the proposal to `stale` and stops;
5. otherwise applies the exact proposed bodies as one transaction;
6. moves the proposal to applied status.

This is the time-of-check/time-of-use protection: human approval attaches to an exact version of the base knowledge.

## Direct-write enforcement

The plugin registers a `pre_tool_call` hook.

By default:

- `write_file`/`patch` targeting governed files inside the knowledge root are blocked and told to retry through `librarian_change`;
- applying a proposal requires native approval;
- configuration changes require native approval;
- obvious shell mutations naming the canonical root are escalated to approval.

The shell check is intentionally conservative. See `security.md`.

## Hermes guidance

The plugin registers:

- a short durable system-prompt section when supported;
- a fallback first-turn hook for older builds;
- the namespaced `librarian` skill with the full workflow;
- a `/librarian` slash command.

This keeps governance discoverable without forking the built-in `llm-wiki` skill.
