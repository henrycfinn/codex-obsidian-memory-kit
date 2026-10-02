"""Codex command-line adapter for the Agentic Librarian core."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from librarian_core import service
from librarian_core.config import LibrarianConfig, discover_knowledge_root


def _emit(value: str | dict[str, Any]) -> None:
    print(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def _load_request(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read request JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("request JSON must be an object")
    return payload


def _config(args: argparse.Namespace) -> LibrarianConfig:
    if args.runtime_home:
        os.environ["HERMES_HOME"] = str(Path(args.runtime_home).expanduser())
    return LibrarianConfig(
        knowledge_root=discover_knowledge_root(args.knowledge_root),
        policy_mode=args.policy_mode,
        qmd_duplicate_check=not args.no_qmd_duplicate_check,
        qmd_sync=args.qmd_sync,
        git_checkpoint=args.git_checkpoint,
        enforce_direct_writes=False,
        guard_terminal_writes=False,
        prompt_guidance=False,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--knowledge-root", help="Canonical Markdown/Obsidian root. Defaults to existing safe discovery.")
    root.add_argument("--runtime-home", help="Hermes home for shared proposals and receipts (defaults to HERMES_HOME or ~/.hermes).")
    root.add_argument("--policy-mode", choices=("strict", "balanced", "autonomous"), default="balanced")
    root.add_argument("--qmd-sync", choices=("off", "update", "update_and_embed"), default="off")
    root.add_argument("--git-checkpoint", action="store_true")
    root.add_argument("--no-qmd-duplicate-check", action="store_true")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("doctor")
    change = commands.add_parser("change")
    change.add_argument("--request", required=True, help="JSON object accepted by librarian_change.")
    review = commands.add_parser("review")
    review.add_argument("--limit", type=int, default=20)
    get = commands.add_parser("get")
    get.add_argument("--proposal-id", required=True)
    get.add_argument("--include-content", action="store_true")
    apply = commands.add_parser("apply")
    apply.add_argument("--proposal-id", required=True)
    apply.add_argument("--approve", action="store_true", help="Required after explicit user approval in Codex.")
    reject = commands.add_parser("reject")
    reject.add_argument("--proposal-id", required=True)
    reject.add_argument("--reason", default="rejected by user")
    history = commands.add_parser("history")
    history.add_argument("--limit", type=int, default=10)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    config = _config(args)
    if args.command == "status":
        _emit(service.status(config))
    elif args.command == "doctor":
        _emit(service.doctor(config))
    elif args.command == "change":
        try:
            request = _load_request(args.request)
        except ValueError as exc:
            _emit({"error": str(exc)})
            return 2
        _emit(service.change(config, request))
    elif args.command == "review":
        _emit(service.review_queue(config, {"limit": args.limit}))
    elif args.command == "get":
        _emit(service.get_proposal_tool(config, {"proposal_id": args.proposal_id, "include_content": args.include_content}))
    elif args.command == "apply":
        if not args.approve:
            _emit({"error": "Refusing to apply without --approve after explicit human approval."})
            return 2
        _emit(service.apply_proposal(config, {"proposal_id": args.proposal_id}))
    elif args.command == "reject":
        _emit(service.reject_proposal(config, {"proposal_id": args.proposal_id, "reason": args.reason}))
    elif args.command == "history":
        _emit(service.history(config, {"limit": args.limit}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
