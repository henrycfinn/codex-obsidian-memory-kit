---
name: codex-librarian
description: Govern Codex writes to a shared Markdown or Obsidian knowledge base with Agentic Librarian's deterministic risk policy, staged review queue, stale-base protection, and receipts. Use when a Codex task would create, update, reorganize, or delete durable wiki knowledge alongside Hermes.
---

# Codex Librarian

Use Agentic Librarian as the only write path for durable knowledge in the canonical wiki. It shares Hermes's proposal and receipt store by default, so either agent can inspect the same review queue.

Set `CODEX_LIBRARIAN_REPO` to the local repository clone. Invoke the adapter with the canonical root explicitly:

```powershell
python "$env:CODEX_LIBRARIAN_REPO\scripts\codex_librarian.py" --knowledge-root <canonical-wiki-path> status
```

## Workflow

1. Search and read task-relevant canonical notes before planning a durable change.
2. Create a JSON request outside the knowledge root. Include a concise `summary`, complete desired contents for each `write`, and semantic `risk_flags` for decisions, conflicts, uncertainty, schema changes, merges, renames, or deletes.
3. Run `change --request <request.json>`. Do not write directly to the canonical root with `apply_patch`, editor commands, or shell redirection.
4. If the result is `applied`, verify the canonical files and report the receipt.
5. If the result is `review_required`, treat it as a user-facing review alert, not a background queue item. Inspect `get --proposal-id <id>`, then immediately show the human a compact table as the primary review surface: **Article** (render per-file `review_page` as the clickable proposed-vs-current diff), **What changes** (use `change_summary`, add/remove counts, and the reason for review), and an optional **Current article** link (render the preview-safe `current_page`, not `markdown_path`). The overall `review_page` remains a color-coded all-files diff: green additions, red deletions, and black unchanged context. Use readable article titles as link labels, never opaque generated filenames. Show visible before/after content inline only for deletions or when requested; never ask a human to approve a deletion without showing the content being deleted. Use the card's short natural-language approve/reject replies; resolve the proposal ID yourself from the active card. Where the host exposes native approval buttons, route final application through that gate; otherwise preserve the short text fallback. Do not claim a separate desktop notification or approval inbox exists.
6. After explicit approval, run `apply --proposal-id <id> --approve`. A changed base produces `stale`; reread affected notes and submit a fresh transaction.

## Commands

```powershell
python "$env:CODEX_LIBRARIAN_REPO\scripts\codex_librarian.py" --knowledge-root <canonical-wiki-path> doctor
python "$env:CODEX_LIBRARIAN_REPO\scripts\codex_librarian.py" --knowledge-root <canonical-wiki-path> review
python "$env:CODEX_LIBRARIAN_REPO\scripts\codex_librarian.py" --knowledge-root <canonical-wiki-path> change --request <request.json>
python "$env:CODEX_LIBRARIAN_REPO\scripts\codex_librarian.py" --knowledge-root <canonical-wiki-path> get --proposal-id <id>
python "$env:CODEX_LIBRARIAN_REPO\scripts\codex_librarian.py" --knowledge-root <canonical-wiki-path> apply --proposal-id <id> --approve
```

Keep QMD synchronization off unless the user requests it. Never place request JSON, proposal bodies, or receipts in the canonical wiki.
