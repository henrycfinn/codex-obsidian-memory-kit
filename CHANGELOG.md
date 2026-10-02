# Changelog

All notable changes to this project will be documented here.

## [1.1.0] - 2026-10-02

- Added a Codex CLI adapter and Codex skill that reuse the existing Librarian policy, staged proposal queue, stale-base checks, and receipts alongside Hermes.
- Added a compact review card to every staged proposal, with reasons, per-file line counts, and exact approve/reject/full-diff responses that agents must surface immediately.
- Review cards now show the actual before/after content for small changes, including deleted content, and use short natural-language decisions instead of proposal IDs.
- Each staged proposal now has readable, per-file proposed-versus-current HTML pages with additions in green, deletions in red, and unchanged context in black.
- Review cards now use a linked article/change-summary table as the primary surface; preview-safe current-article pages avoid blocked raw local Markdown links in Hermes clients.
- Added Windows batch-launcher compatibility for optional QMD commands.

## [1.0.3] - 2026-09-12

- Fixed Windows QMD duplicate-search invocation to use the resolved `qmd.cmd` wrapper.

## [1.0.2] - 2026-09-12

- Fixed Windows QMD discovery and subprocess invocation by preferring the launchable `qmd.cmd` wrapper.

## [1.0.1] - 2026-09-11

- Fixed startup on Hermes hosts that can load Python plugins but do not expose the native settings bridge.
- Added clear diagnostics when setup/configuration is attempted on such a host.
- Added regression coverage for legacy plugin contexts while preserving current Hermes settings behavior.

## [1.0.0] - 2026-09-07

- First public release with native Hermes setup, diagnostics, governance, proposal integrity, and cross-platform atomic writes.

## [0.1.1] - 2026-09-07

- Proposal envelope integrity hashes and tamper refusal.
- Root-filtered queue/history limits.
- Preservation of BOMs, line endings, and file modes during atomic writes.
- Deterministic librarian doctor diagnostics.

## [0.1.0] - 2026-09-07

### Added

- Native Hermes plugin with eight Librarian tools.
- Balanced, strict, and autonomous governance modes.
- Deterministic change/diff risk classification.
- Durable review proposals stored outside canonical knowledge.
- SHA-256 stale-proposal protection.
- Atomic multi-file writes with rollback attempts.
- Direct Hermes `write_file`/`patch` governance hook.
- Native approval for proposal application and configuration changes.
- Optional Obsidian detection.
- Optional QMD duplicate preflight and opt-in sync.
- Optional clean-repository Git checkpoints.
- Local audit receipts without note bodies.
- Runtime Hermes skill, slash command, human docs, agent docs, and public-repository hygiene checks.
