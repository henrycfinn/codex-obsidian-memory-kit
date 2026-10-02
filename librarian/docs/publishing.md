# Publishing on GitHub

This repository is intentionally ready to live as a standalone public Hermes plugin.

## Suggested repository name

```text
hermes-agentic-librarian
```

A different repository name is fine; the Hermes plugin id remains `agentic-librarian` because that is the `name` in `plugin.yaml`.

## Before first public push

Run:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
python scripts/check_public_repo.py
git diff --check
```

With Hermes installed locally, also run:

```bash
hermes plugins doctor . --ci
```

The repository should not contain real runtime proposal/receipt files, local `.env` data, vault content, user home paths, credentials, or machine-specific examples.

## Create and push

Create an empty public repository in the GitHub UI, then from this source tree:

```bash
git remote add origin https://github.com/<owner>/hermes-agentic-librarian.git
git branch -M main
git push -u origin main
```

HTTPS works equally well if that is your normal Git authentication method.

## Test installation from the public repository

```bash
hermes plugins install <owner>/hermes-agentic-librarian --enable
hermes plugins doctor agentic-librarian --ci
```

Then in Hermes:

```text
/librarian status
```

## First release

After the GitHub install works from a clean machine/profile:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Create a GitHub Release from that tag and use the `1.0.0` section of `CHANGELOG.md` as the starting release notes.

## Discovery

For humans:

- repository description: `Trust-aware autonomous knowledge governance for Hermes Agent — Markdown/Obsidian, optional QMD + Git, no Docker.`
- suggested topics: `hermes-agent`, `obsidian`, `qmd`, `knowledge-base`, `llm`, `agents`, `human-in-the-loop`, `markdown`

For agents:

- keep `AGENTS.md` at repository root;
- keep `llms.txt` at repository root;
- keep the runtime skill under `skills/librarian/SKILL.md`;
- update those files whenever public behavior changes.

## Independence statement

Keep `ACKNOWLEDGEMENTS.md` and the README independence language intact unless there is a factual reason to change it. The project is an independent implementation and does not contain member-only/paywalled kit files.
