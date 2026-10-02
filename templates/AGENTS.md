# Shared Obsidian Memory

The existing Obsidian vault is canonical durable memory. Before a durable change, search and read relevant notes. Never directly edit canonical notes: route writes through the installed `codex-librarian` workflow.

- Treat `review_required` as a staged proposal. Apply only after explicit user approval.
- Keep QMD synchronization off unless the owner explicitly enables it.
- Never store credentials, tokens, cookies, or vault-local proposal bodies in source control.
- Preserve the vault's own schema, frontmatter, links, and folder conventions.

