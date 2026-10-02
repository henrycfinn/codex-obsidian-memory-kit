# Codex Obsidian Memory Kit

This repository is a public, portable distribution. Never commit a user's vault contents, home paths, usernames, secrets, proposal bodies, runtime receipts, or QMD index data.

`librarian/` is imported from Agentic Librarian. Update it only by a deliberate subtree refresh from a released upstream revision. Keep installation tooling generic and default QMD synchronization to off.

Run before publishing:

```powershell
python .\librarian\scripts\check_public_repo.py
python -m unittest discover -s .\librarian\tests -v
```

