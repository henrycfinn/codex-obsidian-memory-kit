# Hermes `llm-wiki` Integration

## Goal

Do not fork or replace Hermes' built-in `llm-wiki` skill.

The existing skill remains responsible for:

- source ingestion;
- synthesis;
- wiki conventions;
- provenance;
- cross-linking;
- index/log maintenance;
- querying and linting.

Agentic Librarian adds a write boundary beneath that behavior.

## Before

```text
llm-wiki reasoning
      │
      ▼
write_file / patch
      │
      ▼
wiki Markdown
```

## With Agentic Librarian

```text
llm-wiki reasoning
      │
      ▼
librarian_change
      │
      ├── routine -> auto apply
      │
      └── risky -> proposal
                    │
                 review
                    │
                    ▼
               exact apply
```

## Why a wrapper is preferable

Hermes can improve `llm-wiki` independently. A separate governance plugin avoids maintaining a fork merely to add approval semantics.

The plugin ships its own runtime skill and a small system-prompt section that tells Hermes to use `librarian_change` for canonical knowledge writes. Direct Hermes file writes into governed paths are blocked by default as defense-in-depth.

## Existing wiki layout

If the user's wiki follows the standard Hermes layout, keep it. Agentic Librarian does not migrate or copy it.

If the user's wiki does not follow that layout, do not impose it. The governance engine only needs a canonical folder and policy patterns.

## Raw sources

The built-in pattern treats raw sources as immutable. Agentic Librarian mirrors that principle generically:

- creating a new raw/source file can be autonomous;
- modifying an existing raw/source file requires review.

Configure `raw_patterns` if the wiki uses a different source folder name.

## Semantic risk

`llm-wiki` may discover conflicts that deterministic text metrics cannot understand. The agent should pass an escalation flag:

```json
{
  "summary": "Update product pricing research",
  "risk_flags": ["conflict"],
  "changes": [ ... ]
}
```

The flag forces review. It cannot force auto-application.

## Review ergonomics

The intended workflow is not to ask before each wiki edit. The `librarian_change` call itself either applies the safe transaction or creates a quiet proposal. A user can review the queue later.

This supports scheduled/bot-mode ingestion: routine changes land automatically while contradictions/destructive maintenance accumulate for selective review.
