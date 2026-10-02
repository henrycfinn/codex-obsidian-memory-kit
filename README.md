# Hermes Agentic Librarian

A local-first, trust-aware governance plugin for **Hermes Agent** knowledge bases.

It adds selective human-in-the-loop review **without turning every wiki edit into an approval prompt**. Routine knowledge work can remain autonomous; destructive, conflicting, low-confidence, or unusually large changes are staged for review.

The plugin is deliberately a **wrapper, not another knowledge system**:

- use any Markdown folder;
- use an existing Obsidian vault without reorganizing it;
- keep using Hermes' built-in `llm-wiki` skill;
- optionally use QMD for retrieval and duplicate preflight;
- optionally use Git for transaction checkpoints;
- no Docker, database, daemon, or web server is required.

> **Status:** early public release (`1.0.0`). Review the [Security & Trust Model](docs/security.md) before relying on it for high-stakes data.

## Why this exists

Agentic knowledge systems have two competing goals:

1. **autonomy** — an agent should be able to file, cross-link, and maintain knowledge without asking permission for every harmless edit;
2. **integrity** — an agent should not silently delete established knowledge, overwrite human policy, promote a contradiction, or apply an old proposal against a page that has since changed.

Agentic Librarian separates those concerns:

```text
                    Hermes
                       │
          research / synthesis / wiki skill
                       │
                       ▼
              librarian_change
                       │
          deterministic preflight
                       │
             ┌─────────┴─────────┐
             │                   │
          LOW RISK            HIGH RISK
             │                   │
             ▼                   ▼
        auto-apply          durable proposal
             │                   │
             │              human reviews
             │                   │
             └─────────┬─────────┘
                       ▼
             canonical Markdown
                       │
               ┌───────┴────────┐
               ▼                ▼
          optional QMD      optional Git
             refresh         checkpoint
```

## What it protects

The default **balanced** policy auto-applies common low-risk work such as:

- new Markdown pages;
- additive updates;
- small bounded edits;
- backlinks, metadata, indexes, and ordinary synthesis.

It stages changes such as:

- deletes;
- modification of an existing raw/source file;
- large rewrites or substantial removal;
- edits to `SCHEMA.md`, `AGENTS.md`, `HERMES.md`, and similar control files;
- agent-declared conflict, contradiction, decision, policy, uncertainty, merge/split/rename, etc.;
- low-confidence or contested material in non-autonomous modes;
- oversized transactions;
- likely duplicate page creation in balanced/strict modes.

Applying a staged proposal **re-hashes its target files and the proposal envelope**. If any target or the staged proposal changed since staging, it is refused rather than being blindly applied.

## Requirements

- Hermes Agent with the native Python plugin system.
- Python standard library only for this plugin.

For Codex, use the included local CLI adapter and `codex-librarian` skill; Hermes itself is not required for Codex to run the policy core.

Optional:

- **Obsidian** — detected from `.obsidian/`; no Obsidian plugin is required.
- **QMD** — read-only duplicate lookup can be used when `qmd` is available.
- **Git** — optional per-transaction checkpoints.

## Install

### Fast setup after installation

After enabling the plugin, run the native Hermes CLI wizard:

```bash
hermes agentic-librarian setup
```

It detects `OBSIDIAN_VAULT_PATH`, `WIKI_PATH`, and an existing `~/wiki`, lets you choose the canonical root, and defaults to the balanced policy. For automation or headless machines, pass the root explicitly:

```bash
hermes agentic-librarian setup --root /path/to/knowledge --non-interactive
hermes agentic-librarian doctor
```

The setup command writes only this plugin's settings through Hermes. It does not create, move, index, or rewrite knowledge files.
### From GitHub

After this repository is published:

```bash
hermes plugins install <owner>/hermes-agentic-librarian --enable
hermes plugins doctor agentic-librarian --ci
```

Then run `hermes agentic-librarian setup` to select the knowledge root.

Restart the active Hermes session/gateway if needed, then run:

```text
/librarian status
```

Hermes supports installing standalone plugins from Git repositories; this repository follows the native `plugin.yaml` + `register(ctx)` layout.

### Local development install

Clone/copy the repository into your Hermes plugin directory:

```bash
mkdir -p ~/.hermes/plugins
cp -R hermes-agentic-librarian ~/.hermes/plugins/agentic-librarian
hermes plugins enable agentic-librarian
hermes plugins doctor agentic-librarian --ci
```

On Windows, copy the folder to the equivalent `%USERPROFILE%\.hermes\plugins\agentic-librarian` location.

## First run

The plugin discovers a knowledge root in this order:

1. plugin setting `knowledge_root`;
2. `OBSIDIAN_VAULT_PATH`;
3. `WIKI_PATH`;
4. an existing `~/wiki` directory.

It never guesses that the current working directory is a knowledge base.

Ask Hermes:

```text
Check Agentic Librarian status and configure my existing knowledge folder if needed.
```

Or use:

```text
/librarian status
```

Changing Librarian configuration uses Hermes' native approval gate.

## Existing Hermes `llm-wiki` users

This is the primary integration target.

Keep `llm-wiki` as the system that knows **how to synthesize and organize knowledge**. Agentic Librarian becomes the system that knows **whether a proposed mutation is safe to apply automatically**.

Instead of:

```text
llm-wiki -> write_file / patch -> wiki
```

use:

```text
llm-wiki -> librarian_change -> policy -> wiki
```

The bundled agent skill teaches Hermes this workflow, and the plugin also injects a short system-prompt section so it is discoverable during normal sessions. Direct Hermes `write_file`/`patch` mutations to unambiguously resolved governed paths are blocked by default and redirected to `librarian_change`.

See [Hermes llm-wiki integration](docs/hermes-llm-wiki.md).

## Recommended Hermes memory architecture

For the strongest local-first setup, use the Obsidian/Markdown vault as canonical memory, QMD as retrieval/index infrastructure, Agentic Librarian as the governed write boundary, and Hermes as the reasoning/orchestration layer.

The full human- and agent-facing design is documented in [Hermes Memory Architecture](docs/memory-architecture.md).

## Obsidian + QMD users

Recommended model:

```text
Obsidian vault = canonical knowledge
QMD            = retrieval / index
Librarian      = write governance
Hermes         = reasoning / synthesis
```

The plugin does **not** copy knowledge into a second database or wiki.

When QMD is installed, new-note preflight uses a fast read-only search to surface likely filename/title duplicates. QMD results are locators; the Markdown file remains authoritative.

Post-write QMD sync is **off by default**. You can opt into:

- `off`
- `update`
- `update_and_embed`

The conservative default matters because QMD collections can be configured with update behavior that belongs to the user, not this plugin.

See [Obsidian + QMD](docs/obsidian-qmd.md).

## Plain Markdown users

Nothing else is required. Point `knowledge_root` at a Markdown folder. The plugin provides:

- deterministic risk classification;
- atomic local writes;
- durable staged proposals;
- stale-proposal protection;
- local receipts;
- filename-similarity duplicate checks.

## Tools exposed to Hermes

| Tool | Purpose |
|---|---|
| `librarian_change` | Submit one coherent knowledge transaction; auto-apply or stage it. |
| `librarian_status` | Check root, policy, integrations, and pending queue. |
| `librarian_doctor` | Run deterministic deployment diagnostics suitable for issue reports and CI. |
| `librarian_review_queue` | List pending proposals. |
| `librarian_get_proposal` | Inspect reasons and unified diffs. |
| `librarian_apply_proposal` | Apply an exact staged proposal after native human approval and stale checks. |
| `librarian_reject_proposal` | Reject while keeping local audit history. |
| `librarian_history` | List receipts without note bodies. |
| `librarian_configure` | Change core plugin settings through native approval. |

## Codex alongside Hermes

Codex uses the same core rather than a parallel knowledge layer. The adapter shares the proposal and receipt store with Hermes, so a risky change staged by Codex remains visible to Hermes and vice versa.

```powershell
$env:CODEX_LIBRARIAN_REPO = 'C:\path\to\Hermes-Agentic-Librarian'
python "$env:CODEX_LIBRARIAN_REPO\scripts\codex_librarian.py" --knowledge-root C:\path\to\knowledge status
```

Install the versioned `skills/codex-librarian` folder in Codex's global skills directory, then start a new Codex task. The skill routes durable knowledge writes through `change --request`, surfaces staged proposals, and requires both explicit user approval and `apply --approve` to mutate a staged proposal. See [Configuration](docs/configuration.md#codex-adapter).

Slash command:

```text
/librarian status
/librarian review
/librarian history
/librarian help
```

## Configuration

Example Hermes configuration shape:

```yaml
plugins:
  enabled:
    - agentic-librarian
  entries:
    agentic-librarian:
      settings:
        knowledge_root: "/path/to/knowledge"
        policy_mode: balanced
        enforce_direct_writes: true
        guard_terminal_writes: true
        qmd_duplicate_check: true
        qmd_sync: off
        git_checkpoint: false
```

Do not put secrets in these settings. The plugin does not require any.

See [Configuration](docs/configuration.md) for every option and recommended profiles.

## Review is a queue with a decision-ready alert

A risky `librarian_change` writes a proposal to profile-scoped plugin data and leaves canonical knowledge unchanged. Its result now includes a compact **review card** designed for fast decisions: readable article-title links to individual proposed-vs-current pages beside plain-English change summaries, plus add/remove counts and review reasons. The optional current-article link opens a preview-safe HTML rendering rather than a raw local Markdown path, because some Hermes clients block direct local-file links. Each review page shows additions in green, deletions in red, and unchanged context in black. An agent must present the compact table immediately; it is not acceptable to make the person discover a queue later or approve a deletion without seeing its contents.

When convenient:

```text
/librarian review
```

or ask:

```text
Review the librarian queue and show me only changes that need a decision.
```

The review card is an in-task alert, not a background desktop notification, email, or a separate approval inbox. The plugin deliberately has no required daemon or hosted service. On Hermes platforms that support native approvals, final application uses the platform's approve/deny controls; the short text response remains the portable fallback. Only `librarian_apply_proposal` mutates knowledge, preserving an explicit boundary for sensitive cases.

## Runtime data

Proposal and receipt data is stored using Hermes' documented plugin-data storage location (with a standalone fallback for tests), conceptually:

```text
$HERMES_HOME/plugin-data/agentic-librarian/
├── proposals/
│   ├── pending/
│   ├── applied/
│   ├── rejected/
│   └── stale/
└── receipts/
```

This is intentionally **outside the knowledge root**, so a search/index tool such as QMD does not accidentally treat unapproved proposals as canonical knowledge.

Pending proposal files contain the proposed text because exact application requires it. Receipts deliberately omit note bodies.

## Privacy

- no telemetry;
- no analytics;
- no account or API key required;
- no network server;
- no user-specific path or configuration is shipped in this repository;
- optional QMD and Git calls execute locally;
- runtime knowledge/proposals never belong in this public source repository.

See [Security & Trust Model](docs/security.md).

## Agent documentation

This repository is designed to be discoverable by both people and coding agents:

- [`AGENTS.md`](AGENTS.md) — implementation invariants and contribution instructions for coding agents;
- [`llms.txt`](llms.txt) — compact machine-readable project map;
- [`skills/librarian/SKILL.md`](skills/librarian/SKILL.md) — runtime workflow for Hermes;
- [`skills/codex-librarian/SKILL.md`](skills/codex-librarian/SKILL.md) — runtime workflow for Codex;
- [`scripts/codex_librarian.py`](scripts/codex_librarian.py) — local Codex CLI adapter;
- [`docs/architecture.md`](docs/architecture.md) — component and transaction model;
- [`docs/configuration.md`](docs/configuration.md) — settings and autonomy modes;
- [`docs/hermes-llm-wiki.md`](docs/hermes-llm-wiki.md) — wrapper integration;
- [`docs/obsidian-qmd.md`](docs/obsidian-qmd.md) — optional retrieval integration;
- [`docs/security.md`](docs/security.md) — trust boundaries and threat model;
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — diagnosis and recovery.
- [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md) — public conceptual influences and independence statement.
- [`docs/publishing.md`](docs/publishing.md) — GitHub release checklist and discovery suggestions.
- [`examples/`](examples/) — generic configuration examples for plain Markdown, `llm-wiki`, and Obsidian + QMD.

## Development

No third-party Python dependency is required for tests:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
python scripts/check_public_repo.py
```

When Hermes is installed locally, also run:

```bash
hermes plugins doctor . --ci
```

## Project principles

1. **Canonical Markdown stays canonical.** No shadow database becomes authoritative.
2. **Search before write.** Retrieval helps avoid fragmentation.
3. **Autonomy is the default for routine work.** Human attention is reserved for meaningful risk.
4. **Risk classification is deterministic.** Model confidence may escalate review but cannot bypass code rules.
5. **Proposals are version-bound.** Stale bases are refused.
6. **Optional means optional.** Obsidian, QMD, and Git improve the experience but are not dependencies.
7. **Local-first and inspectable.** State is plain files; no hosted control plane is required.
8. **Do not fork the user's knowledge structure.** Adapt to existing vaults and wikis.

## Attribution and independence

This is an independent open-source implementation inspired by public discussion of human-in-the-loop/agentic knowledge management patterns and by the capabilities exposed by Hermes Agent. No paywalled Agentic Librarian kit code or files are included or required.

Hermes Agent, Obsidian, and QMD are separate projects/products. This repository is not an official release of or endorsement by their maintainers.

## License

MIT — see [LICENSE](LICENSE).
