# Architecture

The kit is intentionally a composition, not a replacement for Obsidian or QMD.

```text
Codex ── research and synthesis ──> Agentic Librarian ── governed write ──> Obsidian vault
                                        │
                                        ├─ staged proposal / review artifacts
                                        └─ receipt / stale-base verification

QMD ── optional retrieval and duplicate preflight ────────────────────────> Markdown vault
```

The Markdown vault remains canonical. QMD is allowed to locate material but never to supply an unverified claim or become a second source of truth. Proposal and receipt data live outside the vault, preventing unapproved content from entering retrieval.

