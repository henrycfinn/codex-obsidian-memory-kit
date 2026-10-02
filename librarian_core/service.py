"""Core Agentic Librarian service.

This module owns the state transitions:
  propose -> deterministic assessment -> auto-apply OR durable proposal
  durable proposal -> stale check -> exact apply

It contains no Hermes-specific imports, making the trust logic easy to test.
"""

from __future__ import annotations

import difflib
import html
import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import LibrarianConfig
from .integrations import (
    detect_obsidian,
    filesystem_duplicate_candidates,
    git_available,
    git_commit_paths,
    git_is_clean,
    git_repo_root,
    qmd_available,
    qmd_duplicate_candidates,
    qmd_status,
    sync_qmd,
)
from .integrity import atomic_write_text, file_sha256, read_text, sha256_text, transaction_lock
from .paths import is_governed, resolve_inside
from .policy import ChangeAssessment, assess_change
from .store import (
    create_proposal,
    data_root,
    get_proposal,
    list_proposals,
    move_proposal,
    recent_receipts,
    utc_now,
    write_receipt,
    verify_proposal,
)


class StaleBaseError(RuntimeError):
    """Raised when canonical knowledge changes after preflight but before mutation."""

    def __init__(self, stale: list[dict[str, Any]]):
        super().__init__("canonical knowledge changed after preflight")
        self.stale = stale


def _result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _first_heading(content: str) -> str:
    for line in content.splitlines()[:80]:
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _unified_diff(path: str, old: str | None, new: str | None, action: str) -> str:
    old_lines = [] if old is None else old.splitlines(keepends=True)
    new_lines = [] if new is None else new.splitlines(keepends=True)
    if action == "delete":
        new_lines = []
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=3,
    )
    text = "".join(diff)
    return text[:80_000]


def _diff_line_counts(diff: str) -> tuple[int, int]:
    """Return added and removed content-line counts for a unified diff."""
    added = 0
    removed = 0
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def _diff_side_content(diff: str, marker: str) -> str:
    """Extract one changed side of a unified diff, without diff headers."""
    lines: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith(marker):
            lines.append(line[1:])
    return "\n".join(lines).strip()


def _content_preview(content: str, limit: int = 1_500) -> tuple[str, bool]:
    """Return reviewable content for small changes and a safe bounded excerpt otherwise."""
    if len(content) <= limit:
        return content, False
    return content[:limit].rstrip() + "\n…", True


def _first_body_paragraph(content: str) -> str:
    """Extract a short human-readable summary from a Markdown document."""
    after_heading = False
    paragraph: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            after_heading = True
            continue
        if not after_heading:
            continue
        if not line:
            if paragraph:
                break
            continue
        if line.startswith("#") or line.startswith("-") or line.startswith("*"):
            if paragraph:
                break
            continue
        paragraph.append(line)
    return " ".join(paragraph)[:360]


def _review_response(action: str, count: int) -> tuple[str, str]:
    noun = "file" if count == 1 else "files"
    if action == "delete":
        return (
            f"Yes — delete these {count} {noun}.",
            f"No — keep these {count} {noun}.",
        )
    return (
        f"Yes — apply these {count} {noun} changes.",
        f"No — do not apply these {count} {noun} changes.",
    )


def _review_filename(title: str, index: int, suffix: str) -> str:
    """Make review attachments understandable in clients that show file names."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")[:72]
    stem = cleaned or f"article-{index:02d}"
    return f"{index:02d}-{stem}-{suffix}.html"


def _review_pages(
    config: LibrarianConfig,
    proposal_id: str,
    summary: str,
    changes: list[dict[str, Any]],
) -> tuple[str | None, list[str | None], list[str | None]]:
    """Create non-canonical HTML diff pages for a staged proposal and its files."""
    root = config.knowledge_root
    if root is None:
        return None, [None] * len(changes), [None] * len(changes)

    sections: list[str] = []
    individual_pages: list[str | None] = []
    current_pages: list[str | None] = []
    # Isolate a proposal's artifacts so attachment names can be human-readable
    # in clients that ignore Markdown link labels and show only the basename.
    review_folder = data_root() / "reviews" / proposal_id
    header = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Librarian review</title>
<style>
body { font-family: system-ui, sans-serif; margin: 2rem; color: #1f2328; background: #fff; }
h1 { margin-bottom: .25rem; } section { margin: 2rem 0; } pre { white-space: pre-wrap; border: 1px solid #d0d7de; padding: 1rem; background: #f6f8fa; }
.added { color: #116329; background: #dafbe1; display: block; } .removed { color: #cf222e; background: #ffebe9; display: block; }
.context { color: #1f2328; display: block; } .meta { color: #57606a; display: block; }
a { color: #0969da; }
</style></head><body>"""
    for index, change in enumerate(changes, 1):
        path = str(change.get("path", ""))
        try:
            absolute, _ = resolve_inside(root, path)
            current_content = read_text(absolute) or ""
        except (ValueError, OSError):
            current_content = ""
        diff_lines: list[str] = []
        for line in str(change.get("diff", "")).splitlines():
            if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                css_class = "meta"
            elif line.startswith("+"):
                css_class = "added"
            elif line.startswith("-"):
                css_class = "removed"
            else:
                css_class = "context"
            diff_lines.append(f'<span class="{css_class}">{html.escape(line)}</span>')
        change_content = change.get("content")
        proposed_content = change_content if isinstance(change_content, str) else ""
        display_title = _first_heading(proposed_content) or _first_heading(current_content) or Path(path).stem
        title = html.escape(display_title)
        rendered_diff = "\n".join(diff_lines)
        section = f"<section id=\"change-{index}\"><h2>{title}</h2><p class=\"meta\">{html.escape(path)}</p><pre>{rendered_diff}</pre></section>"
        sections.append(section)
        detail_path = review_folder / _review_filename(display_title, index, "proposed-vs-current")
        atomic_write_text(
            detail_path,
            header + f"<h1>Review: {html.escape(summary)}</h1><p>Green = proposed additions; red = deletions; black = unchanged context.</p>" + section + "</body></html>",
        )
        individual_pages.append(str(detail_path))
        current_path = review_folder / _review_filename(display_title, index, "current-article")
        atomic_write_text(
            current_path,
            header + f"<h1>Current article: {title}</h1><p class=\"meta\">{html.escape(path)}</p><pre>{html.escape(current_content)}</pre></body></html>",
        )
        current_pages.append(str(current_path))

    document = header + (
        f"<h1>Review: {html.escape(summary)}</h1><p>Green = proposed additions; red = deletions; black = unchanged context.</p>"
        + "\n".join(sections)
        + "</body></html>"
    )
    review_path = review_folder / "All-articles-proposed-vs-current.html"
    atomic_write_text(review_path, document)
    return str(review_path), individual_pages, current_pages


def _attach_review_pages(
    config: LibrarianConfig,
    review_card: dict[str, Any],
    proposal_id: str,
    summary: str,
    changes: list[dict[str, Any]],
) -> None:
    review_page, file_pages, current_pages = _review_pages(config, proposal_id, summary, changes)
    review_card["review_page"] = review_page
    for item, file_page, current_page in zip(review_card.get("files", []), file_pages, current_pages):
        if isinstance(item, dict):
            item["review_page"] = file_page
            item["current_page"] = current_page


def _review_card(
    proposal_id: str,
    summary: str,
    reasons: list[str],
    changes: list[dict[str, Any]],
    root: Path | None = None,
) -> dict[str, Any]:
    """Build the compact, user-facing decision payload for a staged proposal.

    The proposal body stays in plugin data, but small pending changes must be
    directly reviewable. A human should never be asked to approve a deletion
    without seeing what will disappear.
    """
    files: list[dict[str, Any]] = []
    for change in changes:
        diff = str(change.get("diff", ""))
        added, removed = _diff_line_counts(diff)
        content = change.get("content")
        action = str(change.get("action", "write"))
        before = _diff_side_content(diff, "-")
        after = content if isinstance(content, str) else _diff_side_content(diff, "+")
        preview_source = before if action == "delete" else after
        preview, preview_truncated = _content_preview(preview_source) if preview_source else ("", False)
        title = _first_heading(preview_source)
        if action == "delete":
            change_summary = f"Deletes this article ({removed} lines)."
        elif "placeholder" in before.lower() or "created from durable, actionable newsletter intelligence" in before.lower():
            change_summary = "Replaces the template placeholder with: " + _first_body_paragraph(after)
        else:
            change_summary = "Updates the article with: " + _first_body_paragraph(after)
        markdown_path = None
        if root is not None:
            try:
                absolute, _ = resolve_inside(root, str(change.get("path", "")))
                markdown_path = str(absolute)
            except (ValueError, OSError):
                pass
        files.append(
            {
                "path": change.get("path"),
                "action": action,
                "title": title,
                "added_lines": added,
                "removed_lines": removed,
                "content_label": "Current content to be deleted" if action == "delete" else "Proposed content",
                "content_preview": preview,
                "content_preview_truncated": preview_truncated,
                "markdown_path": markdown_path,
                "change_summary": change_summary.rstrip(),
            }
        )
    actions = {str(file["action"]) for file in files}
    primary_action = "delete" if actions == {"delete"} else "write"
    approve_reply, reject_reply = _review_response(primary_action, len(files))
    return {
        "status": "review_needed",
        "proposal_id": proposal_id,
        "summary": summary,
        "why_review": reasons,
        "change_count": len(files),
        "files": files,
        "review_instruction": "Read the visible content previews before deciding. Request a full diff only when a preview is truncated or you need line-level detail.",
        "decisions": {
            "approve": approve_reply,
            "reject": reject_reply,
            "inspect": f"Show the full diff for proposal {proposal_id}",
        },
    }


def _prepare_changes(
    config: LibrarianConfig,
    changes: list[dict[str, Any]],
    risk_flags: list[str],
) -> tuple[list[dict[str, Any]], list[ChangeAssessment], list[str]]:
    root = config.knowledge_root
    if root is None:
        raise ValueError(
            "No knowledge root configured. Set plugins.entries.agentic-librarian.settings.knowledge_root, "
            "OBSIDIAN_VAULT_PATH, or WIKI_PATH."
        )
    if not root.exists():
        raise ValueError(f"Knowledge root does not exist: {root}")

    prepared: list[dict[str, Any]] = []
    assessments: list[ChangeAssessment] = []
    global_reasons: list[str] = []
    seen_paths: set[str] = set()

    if len(changes) > config.max_auto_changes:
        global_reasons.append("batch_exceeds_auto_limit")

    for raw_change in changes:
        if not isinstance(raw_change, dict):
            raise ValueError("Each change must be an object.")
        requested = raw_change.get("path")
        if not isinstance(requested, str) or not requested.strip():
            raise ValueError("Each change requires a non-empty path.")
        absolute, relative = resolve_inside(root, requested)
        relative_key = relative.as_posix()
        if relative_key in seen_paths:
            raise ValueError(f"Duplicate target in one transaction: {relative_key}")
        seen_paths.add(relative_key)
        if not is_governed(relative, config.governed_extensions, config.excluded_patterns):
            raise ValueError(
                f"Path is not governed by Agentic Librarian: {relative.as_posix()}. "
                "Use the normal Hermes file tools for excluded/non-text files."
            )

        action = str(raw_change.get("action", "write") or "write").lower()
        content = raw_change.get("content")
        if action == "write" and not isinstance(content, str):
            raise ValueError(f"Write change requires string content: {relative.as_posix()}")
        if action == "delete":
            content = None

        old_content = read_text(absolute)
        old_sha = file_sha256(absolute)
        duplicates: list[str] = []
        if action == "write" and old_content is None and relative.suffix.lower() in {".md", ".mdx"}:
            title = _first_heading(content or "")
            if config.qmd_duplicate_check and qmd_available():
                duplicates.extend(qmd_duplicate_candidates(root, relative, title))
            duplicates.extend(filesystem_duplicate_candidates(root, relative, excluded_patterns=config.excluded_patterns))
            duplicates = list(dict.fromkeys(duplicates))[:5]

        combined_flags = list(risk_flags)
        per_change_flags = raw_change.get("risk_flags", [])
        if isinstance(per_change_flags, list):
            combined_flags.extend(str(flag) for flag in per_change_flags)

        assessment = assess_change(
            relative=relative,
            action=action,
            old_content=old_content,
            new_content=content,
            config=config,
            risk_flags=combined_flags,
            possible_duplicates=duplicates,
        )
        assessment.old_sha256 = old_sha
        assessment.new_sha256 = sha256_text(content) if content is not None else None
        assessments.append(assessment)
        prepared.append(
            {
                "path": relative.as_posix(),
                "absolute": str(absolute),
                "action": action,
                "content": content,
                "base_sha256": old_sha,
                "proposed_sha256": assessment.new_sha256,
                "diff": _unified_diff(relative.as_posix(), old_content, content, action),
                "assessment": asdict(assessment),
            }
        )

    if global_reasons:
        for assessment in assessments:
            if assessment.decision == "auto":
                assessment.decision = "review"
            assessment.reasons.extend(r for r in global_reasons if r not in assessment.reasons)
        for item, assessment in zip(prepared, assessments):
            item["assessment"] = asdict(assessment)

    return prepared, assessments, global_reasons


def _apply_exact(
    config: LibrarianConfig,
    prepared: list[dict[str, Any]],
    *,
    summary: str,
    decision: str,
    proposal_id: str | None = None,
) -> dict[str, Any]:
    root = config.knowledge_root
    assert root is not None

    changed_paths: list[str] = []
    git_result: dict[str, Any] = {"attempted": False}

    # The cross-process lock coordinates Librarian instances on the same machine.
    # Base hashes are still rechecked inside the lock: locking alone cannot protect
    # against external editors or processes that do not participate in this protocol.
    with transaction_lock(root):
        stale: list[dict[str, Any]] = []
        for item in prepared:
            absolute = Path(item["absolute"])
            current = file_sha256(absolute)
            expected = item.get("base_sha256")
            if current != expected:
                stale.append({
                    "path": item["path"],
                    "reason": "base_changed_after_preflight",
                    "expected_sha256": expected,
                    "current_sha256": current,
                })
        if stale:
            raise StaleBaseError(stale)

        git_repo = None
        git_clean_before = False
        if config.git_checkpoint and git_available():
            git_repo, git_clean_before = git_is_clean(root)

        before: list[tuple[Path, str | None]] = []
        try:
            for item in prepared:
                absolute = Path(item["absolute"])
                before_content = read_text(absolute)
                before.append((absolute, before_content))
                action = item["action"]
                if action == "delete":
                    if absolute.exists():
                        absolute.unlink()
                else:
                    atomic_write_text(absolute, item["content"])
                changed_paths.append(item["path"])
        except Exception:
            # Roll back only mutations performed by this transaction.
            for absolute, previous in reversed(before):
                try:
                    if previous is None:
                        absolute.unlink(missing_ok=True)
                    else:
                        atomic_write_text(absolute, previous)
                except Exception:
                    pass
            raise

        if config.git_checkpoint:
            if git_repo is None:
                git_result = {"attempted": False, "reason": "not_a_git_repo"}
            elif not git_clean_before:
                git_result = {"attempted": False, "reason": "repo_not_clean_before_transaction"}
            else:
                git_result = git_commit_paths(git_repo, root, changed_paths, summary)

    # QMD may be comparatively slow (especially embedding), so do not hold the
    # canonical write lock during index maintenance. Canonical writes are complete.
    qmd_result = sync_qmd(config.qmd_sync, root)

    receipt_changes = []
    for item in prepared:
        absolute = Path(item["absolute"])
        receipt_changes.append(
            {
                "path": item["path"],
                "action": item["action"],
                "before_sha256": item.get("base_sha256"),
                "after_sha256": file_sha256(absolute),
                "assessment": item.get("assessment", {}),
            }
        )
    transaction_id, _ = write_receipt(
        {
            "timestamp": utc_now(),
            "knowledge_root": str(root.resolve(strict=False)),
            "summary": summary,
            "decision": decision,
            "proposal_id": proposal_id,
            "changes": receipt_changes,
            "git": git_result,
            "git_commit": git_result.get("commit"),
            "qmd": qmd_result,
        }
    )
    return {
        "status": "applied",
        "transaction_id": transaction_id,
        "decision": decision,
        "paths": changed_paths,
        "git": git_result,
        "qmd": qmd_result,
    }


def change(config: LibrarianConfig, args: dict[str, Any]) -> str:
    changes = args.get("changes")
    if not isinstance(changes, list) or not changes:
        return _result({"error": "changes must be a non-empty array"})
    summary = str(args.get("summary", "knowledge update") or "knowledge update")[:300]
    risk_flags = args.get("risk_flags", [])
    if not isinstance(risk_flags, list):
        risk_flags = []
    dry_run = bool(args.get("dry_run", False))

    try:
        prepared, assessments, _ = _prepare_changes(config, changes, [str(x) for x in risk_flags])
    except Exception as exc:
        return _result({"error": str(exc)})

    blocked = [a for a in assessments if a.decision == "block"]
    review = [a for a in assessments if a.decision == "review"]
    assessment_payload = [asdict(a) for a in assessments]

    if blocked:
        return _result({"status": "blocked", "summary": summary, "assessments": assessment_payload})

    if dry_run:
        return _result(
            {
                "status": "dry_run",
                "would_apply": not review,
                "would_require_review": bool(review),
                "summary": summary,
                "assessments": assessment_payload,
                "diffs": {item["path"]: item["diff"] for item in prepared},
            }
        )

    if review:
        proposal_changes = []
        reasons: list[str] = []
        for item in prepared:
            assessment = item["assessment"]
            reasons.extend(assessment.get("reasons", []))
            proposal_changes.append(
                {
                    "path": item["path"],
                    "action": item["action"],
                    "content": item["content"],
                    "base_sha256": item["base_sha256"],
                    "proposed_sha256": item["proposed_sha256"],
                    "diff": item["diff"],
                    "assessment": assessment,
                }
            )
        proposal_id, _ = create_proposal(
            {
                "knowledge_root": str(config.knowledge_root.resolve(strict=False)) if config.knowledge_root else None,
                "summary": summary,
                "reasons": list(dict.fromkeys(reasons)),
                "changes": proposal_changes,
            }
        )
        proposal = get_proposal(proposal_id)
        digest = proposal.get("proposal_sha256", "") if proposal else ""
        review_reasons = list(dict.fromkeys(reasons))
        review_card = _review_card(proposal_id, summary, review_reasons, proposal_changes, config.knowledge_root)
        _attach_review_pages(config, review_card, proposal_id, summary, proposal_changes)
        return _result(
            {
                "status": "review_required",
                "proposal_id": proposal_id,
                "proposal_sha256": digest,
                "proposal_digest": str(digest)[:12],
                "summary": summary,
                "reasons": review_reasons,
                "assessments": assessment_payload,
                "review_card": review_card,
                "message": "No canonical files were changed. Present the review card to the human now; do not wait for them to discover the queue.",
            }
        )

    try:
        result = _apply_exact(config, prepared, summary=summary, decision="auto")
    except StaleBaseError as exc:
        return _result({
            "status": "retry_required",
            "message": "Canonical knowledge changed after preflight. Re-read the affected files and retry the transaction.",
            "stale": exc.stale,
        })
    except Exception as exc:
        return _result({"error": f"transaction failed and rollback was attempted: {exc}"})
    result["assessments"] = assessment_payload
    return _result(result)


def review_queue(config: LibrarianConfig, args: dict[str, Any]) -> str:
    try:
        limit = max(1, min(100, int(args.get("limit", 20))))
    except (TypeError, ValueError):
        limit = 20
    root_key = str(config.knowledge_root.resolve(strict=False)) if config.knowledge_root else None
    proposals = list_proposals(limit, root_key) if root_key else []
    return _result({"status": "ok", "count": len(proposals), "proposals": proposals})


def get_proposal_tool(config: LibrarianConfig, args: dict[str, Any]) -> str:
    proposal_id = str(args.get("proposal_id", ""))
    proposal = get_proposal(proposal_id)
    if proposal is None:
        return _result({"error": "proposal not found"})
    if not verify_proposal(proposal):
        return _result({"status": "blocked", "proposal_id": proposal_id, "message": "Proposal integrity check failed; it may have been modified after staging."})
    current_root = str(config.knowledge_root.resolve(strict=False)) if config.knowledge_root else None
    if current_root is None or proposal.get("knowledge_root") != current_root:
        return _result({"error": "proposal not found for the configured knowledge root"})
    review_card = _review_card(
        proposal_id,
        str(proposal.get("summary", "")),
        [str(reason) for reason in proposal.get("reasons", [])],
        [change for change in proposal.get("changes", []) if isinstance(change, dict)],
        config.knowledge_root,
    )
    _attach_review_pages(
        config,
        review_card,
        proposal_id,
        str(proposal.get("summary", "")),
        [change for change in proposal.get("changes", []) if isinstance(change, dict)],
    )
    include_content = bool(args.get("include_content", False))
    if not include_content:
        proposal = dict(proposal)
        proposal["changes"] = [
            {k: v for k, v in change.items() if k != "content"}
            for change in proposal.get("changes", [])
            if isinstance(change, dict)
        ]
    return _result({"status": "ok", "proposal": proposal, "review_card": review_card})


def apply_proposal(config: LibrarianConfig, args: dict[str, Any]) -> str:
    root = config.knowledge_root
    if root is None:
        return _result({"error": "knowledge root is not configured"})
    proposal_id = str(args.get("proposal_id", ""))
    proposal = get_proposal(proposal_id)
    if proposal is None:
        return _result({"error": "proposal not found"})
    if not verify_proposal(proposal):
        return _result({"status": "blocked", "proposal_id": proposal_id, "message": "Proposal integrity check failed; it may have been modified after staging."})

    proposal_root = proposal.get("knowledge_root")
    current_root = str(root.resolve(strict=False))
    if proposal_root and proposal_root != current_root:
        return _result({
            "status": "blocked",
            "proposal_id": proposal_id,
            "message": "Proposal belongs to a different knowledge root. Reconfigure to the original root or create a fresh proposal."
        })

    prepared: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    for change_item in proposal.get("changes", []):
        if not isinstance(change_item, dict):
            continue
        try:
            absolute, relative = resolve_inside(root, str(change_item.get("path", "")))
        except Exception as exc:
            stale.append({"path": change_item.get("path"), "reason": str(exc)})
            continue
        current = file_sha256(absolute)
        expected = change_item.get("base_sha256")
        if current != expected:
            stale.append(
                {
                    "path": relative.as_posix(),
                    "reason": "base_changed_since_proposal",
                    "expected_sha256": expected,
                    "current_sha256": current,
                }
            )
            continue
        prepared.append(
            {
                "path": relative.as_posix(),
                "absolute": str(absolute),
                "action": change_item.get("action", "write"),
                "content": change_item.get("content"),
                "base_sha256": expected,
                "proposed_sha256": change_item.get("proposed_sha256"),
                "diff": change_item.get("diff", ""),
                "assessment": change_item.get("assessment", {}),
            }
        )

    if stale:
        move_proposal(proposal_id, "stale", {"stale_reasons": stale})
        return _result(
            {
                "status": "stale",
                "proposal_id": proposal_id,
                "message": "Proposal was not applied because the underlying knowledge changed after it was staged.",
                "stale": stale,
            }
        )

    try:
        result = _apply_exact(
            config,
            prepared,
            summary=str(proposal.get("summary", "approved knowledge update")),
            decision="human_approved",
            proposal_id=proposal_id,
        )
    except StaleBaseError as exc:
        move_proposal(proposal_id, "stale", {"stale_reasons": exc.stale})
        return _result({
            "status": "stale",
            "proposal_id": proposal_id,
            "message": "Proposal was not applied because the underlying knowledge changed during application preflight.",
            "stale": exc.stale,
        })
    except Exception as exc:
        return _result({"error": f"approved transaction failed and rollback was attempted: {exc}"})

    move_proposal(proposal_id, "applied", {"transaction_id": result.get("transaction_id")})
    return _result(result)


def reject_proposal(config: LibrarianConfig, args: dict[str, Any]) -> str:
    proposal_id = str(args.get("proposal_id", ""))
    proposal = get_proposal(proposal_id)
    current_root = str(config.knowledge_root.resolve(strict=False)) if config.knowledge_root else None
    if proposal is None or current_root is None or proposal.get("knowledge_root") != current_root:
        return _result({"error": "proposal not found for the configured knowledge root"})
    reason = str(args.get("reason", "rejected by user") or "rejected by user")[:1000]
    ok = move_proposal(proposal_id, "rejected", {"rejection_reason": reason})
    if not ok:
        return _result({"error": "proposal not found"})
    return _result({"status": "rejected", "proposal_id": proposal_id})


def history(config: LibrarianConfig, args: dict[str, Any]) -> str:
    try:
        limit = max(1, min(100, int(args.get("limit", 10))))
    except (TypeError, ValueError):
        limit = 10
    root_key = str(config.knowledge_root.resolve(strict=False)) if config.knowledge_root else None
    receipts = recent_receipts(limit, root_key) if root_key else []
    return _result({"status": "ok", "receipts": receipts})


def status(config: LibrarianConfig, args: dict[str, Any] | None = None) -> str:
    del args
    root = config.knowledge_root
    root_key = str(root.resolve(strict=False)) if root else None
    pending = list_proposals(100, root_key) if root_key else []
    qmd = qmd_status() if qmd_available() else {"available": False}
    repo, clean = (None, False)
    if root and root.exists() and git_available():
        repo, clean = git_is_clean(root)
    payload = {
        "status": "ok" if root and root.exists() else "needs_setup",
        "knowledge_root": str(root) if root else None,
        "knowledge_root_exists": bool(root and root.exists()),
        "obsidian_detected": detect_obsidian(root),
        "policy_mode": config.policy_mode,
        "direct_write_enforcement": config.enforce_direct_writes,
        "pending_proposals": len(pending),
        "qmd": qmd,
        "qmd_sync": config.qmd_sync,
        "git": {
            "available": git_available(),
            "repo_detected": repo is not None,
            "clean": clean if repo else None,
            "checkpoint_enabled": config.git_checkpoint,
        },
        "runtime_data": str(data_root()),
    }
    if not root:
        payload["setup_hint"] = (
            "Set plugins.entries.agentic-librarian.settings.knowledge_root, "
            "OBSIDIAN_VAULT_PATH, or WIKI_PATH."
        )
    return _result(payload)


def doctor(config: LibrarianConfig, args: dict[str, Any] | None = None) -> str:
    """Run deterministic deployment checks suitable for issue reports and CI."""
    del args
    root = config.knowledge_root
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("knowledge_root_configured", root is not None, str(root) if root else "No root configured")
    if root is not None:
        add("knowledge_root_exists", root.is_dir(), str(root))
        add("knowledge_root_readable", root.is_dir() and os.access(root, os.R_OK), "read access")
        add("knowledge_root_writable", root.is_dir() and os.access(root, os.W_OK), "write access")
        add("symlink_containment", root.resolve(strict=False).is_dir(), "canonical root resolves")
    runtime = data_root()
    add("plugin_data_writable", runtime.exists() and os.access(runtime, os.W_OK), str(runtime))
    add("policy_configuration", config.policy_mode in {"strict", "balanced", "autonomous"}, config.policy_mode)
    root_key = str(root.resolve(strict=False)) if root else None
    pending = list_proposals(100, root_key) if root_key else []
    add("pending_proposals", True, f"{len(pending)} pending")
    qmd = qmd_status() if qmd_available() else {"available": False}
    add("qmd", not qmd.get("available") or bool(qmd.get("ok")), json.dumps(qmd, ensure_ascii=False))
    repo = git_repo_root(root) if root and git_available() else None
    add("git", not git_available() or root is None or repo is not None, "available or not configured")
    failed = [item["name"] for item in checks if not item["ok"]]
    return _result({"status": "ok" if not failed else "needs_attention", "checks": checks, "failed": failed, "pending_proposals": len(pending)})
