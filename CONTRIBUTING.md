# Contributing

Thanks for improving Agentic Librarian.

Before coding, read [`AGENTS.md`](AGENTS.md) and [`docs/security.md`](docs/security.md). The project is intentionally small; changes that add a server, database, mandatory runtime, or second canonical store need a compelling reason and should normally be an optional adapter instead.

## Development

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
python scripts/check_public_repo.py
```

With Hermes installed:

```bash
hermes plugins doctor . --ci
```

## Pull requests

Please include:

- the user problem;
- why the change fits the canonical-store/autonomy model;
- tests for new risk behavior;
- documentation updates for any user-visible setting/tool/policy change;
- confirmation that public-repo scan and unit tests pass.

Avoid adding dependencies for tasks the Python standard library can handle safely.

## Compatibility

Use documented Hermes plugin APIs only. Do not import Hermes internal modules even when doing so is convenient; internal refactors should not break this plugin.

## Privacy

Never add real vault examples, proposal content, home paths, usernames, emails, tokens, or machine-specific configuration to test fixtures or documentation. Use synthetic fixtures and placeholders.
