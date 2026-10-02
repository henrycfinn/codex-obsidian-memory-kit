# AGENTS.md — Hermes Agentic Librarian

This file is the primary instruction set for coding agents working in this repository.

## Mission

Maintain a small, local-first Hermes plugin that adds **risk-tiered governance** to an existing Markdown knowledge base without replacing that knowledge system.

The plugin must remain useful in all of these configurations:

1. Hermes + plain Markdown folder;
2. Hermes + built-in `llm-wiki`;
3. Hermes + Obsidian vault;
4. Hermes + Obsidian + QMD;
5. any of the above with optional Git checkpoints.

Do not make QMD, Obsidian, Git, Docker, a database, or a daemon mandatory.

## Non-negotiable invariants

### Canonical-store invariant

The configured `knowledge_root` is canonical. The plugin must not introduce a second authoritative knowledge database.

### Proposal isolation invariant

Pending proposal bodies must remain outside `knowledge_root`. Never move `.librarian` proposal data into the vault by default; an indexer could promote unapproved text into retrieval results.

### No bypass-by-confidence invariant

LLM/model-provided `risk_flags` may only **escalate** a change. They must never de-escalate a deterministic review decision.

### Version-bound approval invariant

A staged proposal records the base SHA-256 of every target. `apply_proposal` must re-read and re-hash every target immediately before applying. A mismatch must refuse application and move the proposal to `stale`.

### Atomicity and concurrency invariant

A multi-file auto-apply is one logical transaction. Librarian processes on the same machine coordinate through a root-keyed local lock, and base hashes are rechecked inside the lock immediately before mutation. External/non-participating writers remain outside that lock, so optimistic hashes are still mandatory.

 If a local file write fails mid-transaction, restore all files already changed as far as possible and return an error. Do not report success when only part of the batch landed.

### Raw/source invariant

Creating a new file under configured raw/source patterns may be automatic. Modifying an existing raw/source file requires review.

### Control-file invariant

Human/control files matched by `human_controlled_patterns` require review.

### Optional-integration invariant

Failures in optional QMD synchronization or optional Git checkpointing must be reported in the receipt/result. They must not silently rewrite canonical knowledge or cause a second application of the knowledge transaction.

### Privacy invariant

Never commit:

- real user home paths;
- vault contents;
- proposal/receipt runtime files;
- usernames, emails, tokens, credentials, API keys, or machine IDs;
- `.env` files;
- private configuration copied from a user's Hermes installation.

Use placeholders such as `/path/to/knowledge` and `<owner>` in docs.

## Architecture

- `__init__.py`: Hermes registration boundary only. Register tools/hooks/commands/skill and keep business logic out.
- `schemas.py`: agent-facing tool JSON schemas.
- `librarian_core/config.py`: settings and root discovery.
- `librarian_core/paths.py`: containment and governance matching.
- `librarian_core/policy.py`: deterministic risk classification. Keep pure/testable.
- `librarian_core/service.py`: transaction state machine.
- `librarian_core/store.py`: profile-scoped proposals and receipts.
- `librarian_core/integrity.py`: hashes and atomic writes.
- `librarian_core/integrations.py`: optional local QMD/Obsidian/Git integration.
- `skills/librarian/SKILL.md`: runtime agent instructions.
- `scripts/codex_librarian.py`: Codex CLI adapter; reuse the core and shared proposal/receipt store rather than duplicating policy.
- `skills/codex-librarian/SKILL.md`: Codex runtime workflow.
- `docs/`: human and agent reference material.

## Hermes compatibility

Use documented Hermes plugin surfaces (`ctx.register_tool`, `ctx.register_hook`, `ctx.register_command`, `ctx.register_skill`, `ctx.get_config`, `ctx.set_config`, `ctx.register_system_prompt_section` when available). The documented `plugins.plugin_storage.plugin_data_dir` helper is also permitted for durable plugin files. Avoid undocumented Hermes internal modules.

The repository intentionally keeps a compatibility fallback for Hermes builds that do not expose system prompt sections.

## Codex compatibility

Codex uses `scripts/codex_librarian.py` and the `codex-librarian` skill, not the Hermes plugin registration boundary. The adapter must preserve the core policy, version-bound proposals, and shared runtime storage. It must require an explicit `--approve` after the user approves a staged proposal; Codex sandbox approval alone is not that semantic approval.

Before a release, run `hermes plugins doctor . --ci` on a current Hermes installation. Do not claim compatibility solely from unit tests.

## Security model

Read `docs/security.md` before changing enforcement.

The `pre_tool_call` guard is defense-in-depth for Hermes tools, not an OS sandbox. Do not describe `guard_terminal_writes` as complete shell interception. It intentionally catches only obvious commands targeting the literal configured root.

Do not attempt to implement a shell parser unless there is a rigorous, tested design; false confidence is worse than an explicit boundary.

## Policy behavior

Balanced mode is the product default. Changes to thresholds or classifications require tests documenting the user-visible behavior.

Always review:

- deletes;
- human-controlled files;
- mutation of existing raw/source files;
- batches over `max_auto_changes`;
- explicit high-risk semantic flags.

Balanced/strict additionally review major rewrite/substantial removal and likely duplicate creation. Strict stages non-additive changes to existing files. Autonomous may tolerate likely duplicates but still obey hard protections.

## QMD rules

- QMD is an optional locator/index, never authoritative.
- Duplicate preflight should remain read-only and fast.
- Do not call model-backed retrieval merely as a mandatory write precondition.
- `qmd_sync` defaults to `off`.
- Never execute arbitrary QMD update hooks from plugin configuration created by this repository.
- If QMD output formats change, fail gracefully to no duplicate candidates rather than failing a knowledge write.

## Git rules

- Git checkpoints are opt-in.
- Only checkpoint when the repo is clean **before** the transaction.
- Stage only transaction paths, never `git add -A`.
- Never push, fetch, pull, or alter remotes.
- Failure to commit is an audit-layer failure, not permission to repeat the file writes.

## Testing expectations

Every material change should keep or add tests for:

- path traversal/symlink containment;
- risk classification;
- autonomous apply;
- proposal staging with no canonical mutation;
- stale proposal refusal;
- rollback on partial write failure where practical;
- direct Hermes write guard;
- plugin registration surface;
- public-repository privacy scan.

Run:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
python scripts/check_public_repo.py
```

If Hermes is installed:

```bash
hermes plugins doctor . --ci
```

## Documentation contract

Any new setting, tool, risk rule, or integration must be documented in:

- the relevant human doc under `docs/`;
- `README.md` if it affects installation or primary behavior;
- `skills/librarian/SKILL.md` if runtime agents need to know it;
- `llms.txt` if it changes the project map or central behavior.

## Release checklist

1. Update `CHANGELOG.md` and version in `plugin.yaml`, `librarian_core/constants.py`, and the skill frontmatter.
2. Run all tests and public scan.
3. Run Hermes plugin doctor on current Hermes.
4. Inspect `git diff --check`.
5. Confirm there are no runtime proposal/receipt files in Git.
6. Confirm README install examples still use generic placeholders.
7. Tag `vX.Y.Z` only after the release commit is clean.
