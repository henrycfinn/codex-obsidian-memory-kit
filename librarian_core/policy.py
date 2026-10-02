"""Deterministic risk classification for knowledge-base changes."""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .config import LibrarianConfig
from .constants import RISK_FLAGS_REVIEW
from .paths import matches_any


@dataclass
class ChangeAssessment:
    path: str
    action: str
    decision: str  # auto | review | block
    reasons: list[str] = field(default_factory=list)
    old_sha256: str | None = None
    new_sha256: str | None = None
    changed_ratio: float = 0.0
    removal_ratio: float = 0.0
    additive_only: bool = False
    possible_duplicates: list[str] = field(default_factory=list)


def _line_metrics(old: str, new: str) -> tuple[float, float, bool]:
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    removed = 0
    added = 0
    changed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old_n = i2 - i1
        new_n = j2 - j1
        removed += old_n
        added += new_n
        changed += max(old_n, new_n)
    denominator = max(len(old_lines), len(new_lines), 1)
    changed_ratio = changed / denominator
    removal_ratio = removed / max(len(old_lines), 1)
    additive_only = removed == 0 and added > 0
    return changed_ratio, removal_ratio, additive_only


def assess_change(
    *,
    relative: Path,
    action: str,
    old_content: str | None,
    new_content: str | None,
    config: LibrarianConfig,
    risk_flags: Iterable[str] = (),
    possible_duplicates: Iterable[str] = (),
) -> ChangeAssessment:
    path = relative.as_posix()
    action = action.lower()
    reasons: list[str] = []
    decision = "auto"
    duplicate_list = list(dict.fromkeys(str(x) for x in possible_duplicates if x))

    if action not in {"write", "delete"}:
        return ChangeAssessment(path=path, action=action, decision="block", reasons=["unsupported_action"])

    if matches_any(relative, config.human_controlled_patterns):
        decision = "review"
        reasons.append("human_controlled_path")

    if action == "delete":
        decision = "review"
        reasons.append("delete")
        return ChangeAssessment(path=path, action=action, decision=decision, reasons=reasons)

    if new_content is None:
        return ChangeAssessment(path=path, action=action, decision="block", reasons=["missing_content"])

    if old_content is None:
        if duplicate_list:
            # Only exact/high-confidence path/name matching should reach this list.
            decision = "review" if config.policy_mode != "autonomous" else decision
            reasons.append("possible_duplicate")
        if matches_any(relative, config.raw_patterns):
            reasons.append("new_raw_source")
        else:
            reasons.append("new_page")
    else:
        if matches_any(relative, config.raw_patterns):
            decision = "review"
            reasons.append("raw_source_mutation")

        changed_ratio, removal_ratio, additive_only = _line_metrics(old_content, new_content)
        if removal_ratio >= config.removal_review_ratio:
            decision = "review"
            reasons.append("substantial_removal")
        if changed_ratio >= config.major_rewrite_ratio:
            decision = "review"
            reasons.append("major_rewrite")
        if additive_only:
            reasons.append("additive_update")
        elif changed_ratio > 0:
            reasons.append("bounded_update")

        if config.policy_mode == "strict" and changed_ratio > 0 and not additive_only:
            decision = "review"
            reasons.append("strict_mode_update")

    normalized_flags = {str(flag).strip().lower() for flag in risk_flags if str(flag).strip()}
    escalations = sorted(normalized_flags & RISK_FLAGS_REVIEW)
    if escalations:
        decision = "review"
        reasons.extend(f"agent_flag:{flag}" for flag in escalations)

    # Low-confidence/contested frontmatter is a useful generic signal for llm-wiki users.
    lowered = new_content.lower()
    if "contested: true" in lowered or "confidence: low" in lowered:
        if config.policy_mode != "autonomous":
            decision = "review"
        reasons.append("quality_signal_requires_attention")

    changed_ratio = 0.0
    removal_ratio = 0.0
    additive_only = False
    if old_content is not None:
        changed_ratio, removal_ratio, additive_only = _line_metrics(old_content, new_content)

    return ChangeAssessment(
        path=path,
        action=action,
        decision=decision,
        reasons=list(dict.fromkeys(reasons)),
        changed_ratio=round(changed_ratio, 4),
        removal_ratio=round(removal_ratio, 4),
        additive_only=additive_only,
        possible_duplicates=duplicate_list,
    )
