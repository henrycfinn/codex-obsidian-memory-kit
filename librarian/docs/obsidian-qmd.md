# Obsidian + QMD

## Recommended roles

For users who already use both systems:

```text
Obsidian vault  = canonical human-readable knowledge
QMD             = search/index/retrieval
Hermes          = reasoning and knowledge work
Agentic Librarian = write governance
```

Do not treat a QMD chunk/snippet as the canonical object. Use retrieval to locate the Markdown note, then read that note before making consequential claims or changes.

## Obsidian

The plugin detects a vault when `.obsidian/` exists under `knowledge_root`.

It does not require an Obsidian community plugin and does not edit `.obsidian/` by default.

Existing folder organization is respected. A mature vault should not be migrated merely to satisfy a plugin taxonomy.

## QMD duplicate preflight

If `qmd` is on PATH and `qmd_duplicate_check` is enabled, the plugin performs a read-only search before creating a new Markdown file.

The result is deliberately conservative:

1. QMD returns candidate paths;
2. the plugin filters to files inside the canonical root;
3. filename/title-stem similarity is checked deterministically;
4. strong candidates are surfaced as `possible_duplicate`.

In balanced/strict modes, that stages the creation for review. In autonomous mode it is recorded but not automatically escalated.

If QMD is unavailable or its output changes, the plugin falls back to a dependency-free filesystem filename check. QMD failure must not make the knowledge base unusable.

## Why not run model-backed QMD retrieval on every write?

Governance should remain fast, predictable, and available without loading a retrieval model. The plugin therefore uses a lightweight search for duplicate preflight and leaves deeper QMD querying to Hermes when semantic retrieval is actually useful.

## Post-write sync

Default:

```yaml
qmd_sync: off
```

Optional modes:

```yaml
qmd_sync: update
```

or:

```yaml
qmd_sync: update_and_embed
```

Sync happens once after the coherent multi-file knowledge transaction, not after each file.

## Why sync is opt-in

QMD is user-configurable. Index maintenance can have local cost and collection update behavior belongs to the user's environment. A public governance plugin should not automatically enable command execution or heavyweight embedding work simply because QMD is detected.

## Preventing proposal contamination

Pending proposals are written under Hermes plugin data, not inside the vault. Do not configure QMD to index the Agentic Librarian plugin-data directory as canonical knowledge.

If a user deliberately creates a QMD collection over all of their home directory, they should explicitly exclude Hermes runtime/plugin-data paths.
