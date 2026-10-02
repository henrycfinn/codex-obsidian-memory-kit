## Summary

What user problem does this change solve?

## Trust impact

- [ ] Canonical Markdown remains the only authoritative store.
- [ ] Model-provided signals cannot weaken deterministic safeguards.
- [ ] Proposal isolation and stale-base checks remain intact.
- [ ] Optional integrations remain optional.
- [ ] No private/user-specific data was added.

## Validation

- [ ] `python -m compileall -q .`
- [ ] `python -m unittest discover -s tests -v`
- [ ] `python scripts/check_public_repo.py`
- [ ] `hermes plugins doctor . --ci` (when Hermes is available)
- [ ] Relevant docs were updated.
