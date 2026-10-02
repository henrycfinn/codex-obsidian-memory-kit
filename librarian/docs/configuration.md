# Configuration

Settings live in Hermes' plugin-scoped configuration under `plugins.entries.agentic-librarian.settings`.

## Codex adapter

Codex can use the same core without loading the Hermes plugin. Run the local adapter with the canonical root explicitly:

```powershell
python scripts/codex_librarian.py --knowledge-root /path/to/knowledge status
```

The adapter uses the same `HERMES_HOME/plugin-data/agentic-librarian` proposal and receipt store by default, so Codex and Hermes can inspect the same queue. Set `--runtime-home /path/to/hermes-home` when the Hermes home is not available through `HERMES_HOME` or the default location.

`apply` requires `--approve` in addition to normal Codex filesystem approval. Use that flag only after the user has explicitly approved the staged proposal. Its defaults remain balanced policy, QMD sync off, and Git checkpoints off.

### Codex review notifications

When a Codex-routed change returns `review_required`, the Codex Librarian skill treats it as an immediate in-task notification. It retrieves the staged proposal and presents a compact review table with:

- a per-article link to a proposed-versus-current color diff;
- a plain-English summary of each change, plus added/removed line counts;
- an optional preview-safe rendering of the current article (rather than a raw local Markdown link that some clients block); and
- short natural-language approve or reject responses.

The generated review pages are stored outside the knowledge root with the proposal data, so unapproved text cannot enter the canonical wiki or QMD retrieval. Codex does not expose a plugin API for an independent desktop toast or custom button widget; the review card in the active task is the portable notification surface.

## Root discovery

If `knowledge_root` is empty, the plugin checks in order:

1. `OBSIDIAN_VAULT_PATH`
2. `WIKI_PATH`
3. an existing `~/wiki`

The plugin does not silently use the current working directory.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `knowledge_root` | empty | Canonical folder. Empty enables safe auto-discovery. |
| `policy_mode` | `balanced` | `strict`, `balanced`, or `autonomous`. |
| `enforce_direct_writes` | `true` | Block Hermes `write_file`/`patch` to governed files so they use the Librarian. |
| `guard_terminal_writes` | `true` | Escalate obvious shell mutations naming the root. Defense-in-depth only. |
| `governed_extensions` | Markdown/text extensions | Which text files are governed. |
| `excluded_patterns` | Obsidian/Git/trash metadata | Paths ignored by governance. |
| `raw_patterns` | common raw/source folders | Existing files in these paths are immutable without review. |
| `human_controlled_patterns` | schema/agent instruction files | Always require review. |
| `major_rewrite_ratio` | `0.35` | Changed-line fraction that triggers review. |
| `removal_review_ratio` | `0.15` | Removed-line fraction that triggers review. |
| `max_auto_changes` | `20` | Larger coherent batches are reviewed. |
| `qmd_duplicate_check` | `true` | Use QMD read-only search for likely duplicate filenames/titles when available. |
| `qmd_sync` | `off` | `off`, `update`, or `update_and_embed`. |
| `git_checkpoint` | `false` | Commit a transaction when the Git repo was clean beforehand. |
| `prompt_guidance` | `true` | Teach Hermes to route knowledge writes through Librarian. |

## Policy modes

### Balanced — recommended

Designed for most personal/team knowledge bases.

Auto:

- new pages that do not look like duplicates;
- additive updates;
- bounded small updates;
- ordinary metadata/index/backlink edits.

Review:

- deletes;
- source mutation;
- large rewrites/removal;
- control files;
- likely duplicates;
- explicit semantic risk flags;
- low-confidence/contested signals;
- oversized transactions.

### Strict

Adds review for non-additive changes to existing files. Use when preserving the exact prior wording matters more than minimizing review workload.

### Autonomous

Removes some soft review triggers, such as likely duplicate creation and low-confidence frontmatter, but retains hard safeguards such as deletion review, protected control files, raw-source mutation, and deterministic rewrite/removal thresholds.

`autonomous` does not mean unrestricted filesystem writes.

## Human-controlled content

For a wiki with durable decisions or policies, add patterns such as:

```yaml
human_controlled_patterns:
  - "SCHEMA.md"
  - "**/SCHEMA.md"
  - "Decisions/**"
  - "Policies/**"
```

The public default intentionally avoids domain-specific paths.

## QMD sync

Keep `qmd_sync: off` initially.

If QMD is already configured and you trust its local collection/update behavior:

```yaml
qmd_sync: update
```

or:

```yaml
qmd_sync: update_and_embed
```

A transaction batches all related wiki changes and then performs at most one configured QMD refresh.

## Git checkpoints

When enabled:

```yaml
git_checkpoint: true
```

Agentic Librarian only creates a commit if the repository is clean before the knowledge transaction. It stages only paths in that transaction. It never pushes or changes remotes.

If the repository is already dirty, the knowledge write can still occur but the checkpoint is skipped and reported. This avoids accidentally bundling unrelated human work into an automated commit.
