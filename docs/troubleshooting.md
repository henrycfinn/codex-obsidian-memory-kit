# Troubleshooting

## `knowledge root is not configured`

Run:

```text
/librarian status
```

The plugin auto-detects `OBSIDIAN_VAULT_PATH`, `WIKI_PATH`, or an existing `~/wiki`. Otherwise configure an existing folder through `librarian_configure` or Hermes plugin settings.

## Hermes tries `write_file` and gets blocked

This is expected inside governed knowledge files. The model should retry the complete desired mutation through `librarian_change`.

Load the runtime skill if needed:

```text
agentic-librarian:librarian
```

If a third-party skill repeatedly bypasses governance, keep direct-write enforcement enabled and update that skill's instructions to call `librarian_change` for canonical writes.

## Too many proposals

First inspect why:

```text
/librarian review
```

Common causes:

- `major_rewrite_ratio` is too low for the wiki's formatting style;
- a frequently edited directory is in `human_controlled_patterns`;
- the agent is overusing semantic risk flags;
- the same topic has duplicate filenames;
- `strict` mode is enabled.

For most users, start with `balanced` rather than disabling safeguards.

## Too much autonomy

Switch to `strict`, lower rewrite/removal thresholds, or add important directories to `human_controlled_patterns`.

Do not rely on prompt wording alone when a deterministic path policy can express the requirement.

## Proposal became stale

This is a safety feature. A target note changed after the proposal was staged, so approval no longer applies to the same base.

Re-run the original knowledge task against the current note and create a fresh proposal if the change is still needed.

## QMD not detected

QMD is optional. The plugin continues with filesystem duplicate checking.

If expected, verify `qmd` is on PATH in the same environment that launches Hermes.

## QMD index is not refreshed

`qmd_sync` defaults to `off`. Enable `update` or `update_and_embed` only after confirming your QMD setup is safe to invoke automatically.

The plugin reports QMD sync results in the transaction receipt/status rather than pretending a failed refresh succeeded.

## Git checkpoint skipped

Expected reasons include:

- Git is not installed;
- the knowledge root is not inside a Git repository;
- `git_checkpoint` is false;
- the repository had unrelated uncommitted changes before the transaction.

The plugin intentionally refuses to commit a dirty repo because doing so could capture unrelated user work.

## Plugin does not load

Run current Hermes diagnostics:

```bash
hermes plugins doctor . --ci
hermes plugins list
```

This project avoids imports from Hermes internal modules and uses the documented plugin context surface.

### `PluginContext` has no attribute `get_config`

This indicates an older or partially upgraded Hermes host. Agentic Librarian 1.0.1 can register safely on that host, but persistent plugin settings and the setup wizard require Hermes' native settings bridge. Upgrade/restart Hermes so the backend and Desktop use the same release, then rerun:

```text
hermes plugins doctor agentic-librarian --ci
hermes agentic-librarian setup --root /path/to/knowledge --non-interactive
```

Until upgraded, root discovery can still use `OBSIDIAN_VAULT_PATH`, `WIKI_PATH`, or an existing `~/wiki`; configuration changes are intentionally refused rather than written through undocumented APIs.

## QMD reports `WinError 2` on Windows

Agentic Librarian 1.0.3 prefers the launchable `qmd.cmd` wrapper when QMD is installed through npm. Restart Hermes after upgrading the plugin, then rerun `librarian_doctor`. If QMD is still unavailable, verify `qmd.cmd` is on the PATH of the process launching Hermes.

## Direct shell command bypassed the plugin

The shell guard is not a security sandbox. It only escalates obvious commands that directly reference the canonical root. See `docs/security.md`.

Use the provided Librarian tools for agent workflows and stronger OS-level controls if you need enforcement against arbitrary local processes.
