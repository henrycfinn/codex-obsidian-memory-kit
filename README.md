# Codex Obsidian Memory Kit

A local-first, reviewable memory system for Codex, Obsidian, and optional QMD retrieval.

It keeps Markdown in your Obsidian vault as the source of truth. The included Agentic Librarian governs durable writes: routine changes may apply automatically, while rewrites, deletions, control files, conflicts, and large batches are staged for review with receipts and stale-base protection.

## What is included

- `librarian/` — pinned Agentic Librarian source and Codex adapter.
- `scripts/setup.ps1` — installs the Codex workflow and configures a local environment variable; it never writes into your vault.
- `templates/` — safe starter instructions and an optional vault landing note.
- `docs/` — architecture, QMD guidance, and operational boundaries.

## Quick start (Windows)

1. Clone this repository.
2. Open PowerShell in the repository and run:

   ```powershell
   .\scripts\setup.ps1 -KnowledgeRoot C:\path\to\your\ObsidianVault
   ```

3. Start a new Codex task in a repository that contains the included `AGENTS.md` guidance, or paste the workflow from `templates/AGENTS.md` into your project's instructions.
4. Ask Codex to improve a note. Durable vault writes are routed through the Librarian.

The setup script copies the bundled `codex-librarian` skill into your Codex skills directory and sets `CODEX_LIBRARIAN_REPO` to this repository's `librarian` folder for your user account. Restart Codex after setup.

## The memory model

| Layer | Responsibility |
| --- | --- |
| Obsidian / Markdown | Canonical, human-readable memory |
| Agentic Librarian | Governed writes, proposals, approvals, receipts, stale-base checks |
| Codex | Research, synthesis, and tool use |
| QMD (optional) | Retrieval and duplicate preflight; never authoritative |

See [architecture](docs/architecture.md) and [QMD guidance](docs/qmd.md).

## Safety promises

- No hosted database, telemetry, or required account beyond the tools you already use.
- No durable vault write bypasses the Librarian workflow.
- Pending proposal bodies stay outside the vault, so unapproved text is not retrieved as memory.
- QMD synchronization stays off unless you explicitly enable it.
- The kit contains no vault contents, usernames, API keys, or machine-specific paths.

## Updating the included Librarian

`librarian/` is a Git subtree pinned to a tested Agentic Librarian release. Refresh it deliberately after reviewing upstream release notes; do not edit its policy code independently in this repository.

## License

MIT. The included Librarian subtree retains its own license and notices.

