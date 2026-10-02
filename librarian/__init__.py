"""Agentic Librarian Hermes plugin registration."""

from __future__ import annotations

import json
import argparse
import logging
import os
import re
from pathlib import Path
from typing import Any

from . import schemas
from .librarian_core.config import has_settings_bridge, load_config
from .librarian_core.constants import TERMINAL_MUTATION_MARKERS, TOOLSET
from .librarian_core.paths import is_governed, resolve_inside
from .librarian_core import service

logger = logging.getLogger(__name__)

_V4A_PATH_RE = re.compile(r"^\*\*\*\s*(?:Update|Add|Delete)\s+File:\s*(.+?)\s*$", re.MULTILINE)
_V4A_MOVE_RE = re.compile(r"^\*\*\*\s*Move\s+File:\s*(.+?)\s*->\s*(.+?)\s*$", re.MULTILINE)


def _json_error(message: str) -> str:
    return json.dumps({"error": message})


def _candidate_paths(tool_name: str, args: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    if isinstance(args.get("path"), str):
        paths.append(args["path"])
    if tool_name == "patch" and isinstance(args.get("patch"), str):
        patch_text = args["patch"]
        paths.extend(match.group(1).strip() for match in _V4A_PATH_RE.finditer(patch_text))
        for match in _V4A_MOVE_RE.finditer(patch_text):
            paths.extend([match.group(1).strip(), match.group(2).strip()])
    return list(dict.fromkeys(paths))


def _inside_governed_root(config, requested: str) -> bool:
    root = config.knowledge_root
    if root is None:
        return False

    expanded = Path(os.path.expandvars(str(requested))).expanduser()
    if not expanded.is_absolute():
        # Hermes file tools resolve relative paths against task/session cwd, which the
        # public plugin hook does not expose as a stable path API. Avoid blocking
        # unrelated relative Markdown writes. When the process cwd is the knowledge
        # root, the path is unambiguous and can be protected.
        try:
            if Path.cwd().resolve(strict=False) != root.resolve(strict=False):
                return False
            expanded = Path.cwd() / expanded
        except OSError:
            return False
    try:
        _, relative = resolve_inside(root, expanded)
    except (ValueError, OSError):
        return False
    return is_governed(relative, config.governed_extensions, config.excluded_patterns)


def _register_tools(ctx):
    handlers = {
        "librarian_change": lambda args, **kwargs: service.change(load_config(ctx), args),
        "librarian_status": lambda args, **kwargs: service.status(load_config(ctx), args),
        "librarian_doctor": lambda args, **kwargs: service.doctor(load_config(ctx), args),
        "librarian_review_queue": lambda args, **kwargs: service.review_queue(load_config(ctx), args),
        "librarian_get_proposal": lambda args, **kwargs: service.get_proposal_tool(load_config(ctx), args),
        "librarian_apply_proposal": lambda args, **kwargs: service.apply_proposal(load_config(ctx), args),
        "librarian_reject_proposal": lambda args, **kwargs: service.reject_proposal(load_config(ctx), args),
        "librarian_history": lambda args, **kwargs: service.history(load_config(ctx), args),
    }

    def configure(args: dict[str, Any], **kwargs) -> str:
        del kwargs
        try:
            if not has_settings_bridge(ctx):
                return _json_error("This Hermes host can load Agentic Librarian but does not expose the native plugin settings bridge. Upgrade Hermes or configure knowledge_root through a supported host before using librarian_configure.")
            if "knowledge_root" in args:
                root = Path(str(args["knowledge_root"])).expanduser().resolve(strict=False)
                if not root.is_dir():
                    return _json_error(f"knowledge_root must be an existing directory: {root}")
                ctx.set_config("knowledge_root", str(root))
            if "policy_mode" in args:
                value = str(args["policy_mode"])
                if value not in {"strict", "balanced", "autonomous"}:
                    return _json_error("policy_mode must be strict, balanced, or autonomous")
                ctx.set_config("policy_mode", value)
            if "qmd_sync" in args:
                value = str(args["qmd_sync"])
                if value not in {"off", "update", "update_and_embed"}:
                    return _json_error("qmd_sync must be off, update, or update_and_embed")
                ctx.set_config("qmd_sync", value)
            if "git_checkpoint" in args:
                ctx.set_config("git_checkpoint", bool(args["git_checkpoint"]))
            if "enforce_direct_writes" in args:
                ctx.set_config("enforce_direct_writes", bool(args["enforce_direct_writes"]))
            return service.status(load_config(ctx), {})
        except Exception as exc:
            return _json_error(str(exc))

    handlers["librarian_configure"] = configure

    for schema in schemas.ALL_SCHEMAS:
        name = schema["name"]
        ctx.register_tool(name=name, toolset=TOOLSET, schema=schema, handler=handlers[name])


def _register_hooks(ctx):
    def guard_tool_call(tool_name: str, args: dict, **kwargs):
        del kwargs
        config = load_config(ctx)

        if tool_name in {"librarian_apply_proposal", "librarian_configure"}:
            if tool_name == "librarian_apply_proposal":
                proposal_id = str(args.get("proposal_id", "unknown"))
                return {
                    "action": "approve",
                    "message": f"Apply reviewed knowledge proposal {proposal_id}. Exact base hashes will be rechecked before write.",
                    "rule_key": "agentic-librarian:apply-proposal",
                }
            return {
                "action": "approve",
                "message": "Change Agentic Librarian governance configuration.",
                "rule_key": "agentic-librarian:configure",
            }

        root = config.knowledge_root
        if root is None:
            return None

        if config.enforce_direct_writes and tool_name in {"write_file", "patch"}:
            protected = [p for p in _candidate_paths(tool_name, args) if _inside_governed_root(config, p)]
            if protected:
                shown = ", ".join(protected[:3])
                return {
                    "action": "block",
                    "message": (
                        f"Agentic Librarian protects this knowledge path ({shown}). "
                        "Retry through librarian_change so the update receives deterministic risk classification, receipts, and review staging when needed."
                    ),
                }

        if config.guard_terminal_writes and tool_name == "terminal":
            command = str(args.get("command", ""))
            root_text = str(root)
            # This is deliberately conservative, not a shell parser. It catches obvious
            # bypasses while documenting that external processes are outside the trust boundary.
            if root_text and root_text in command and any(marker in command for marker in TERMINAL_MUTATION_MARKERS):
                return {
                    "action": "approve",
                    "message": "Shell command appears to mutate the governed knowledge root outside librarian_change.",
                    "rule_key": "agentic-librarian:terminal-write",
                }
        return None

    ctx.register_hook("pre_tool_call", guard_tool_call)


def _register_guidance(ctx):
    config = load_config(ctx)
    if not config.prompt_guidance:
        return

    def guidance(_session_info=None):
        current = load_config(ctx)
        root = str(current.knowledge_root) if current.knowledge_root else "not configured"
        return (
            "Agentic Librarian is enabled. Canonical knowledge root: " + root + ". "
            "For governed knowledge writes, including work initiated by the built-in llm-wiki skill, use `librarian_change` instead of `write_file`/`patch`. "
            "Safe changes auto-apply; high-risk changes are staged in a review queue. Use `librarian_status` when setup is uncertain and load `agentic-librarian:librarian` for the full workflow."
        )

    if hasattr(ctx, "register_system_prompt_section"):
        ctx.register_system_prompt_section(
            "agentic-librarian.workflow",
            guidance,
            position="after_memory",
            max_chars=1200,
        )
    else:
        # Compatibility fallback for Hermes builds predating system prompt sections.
        def first_turn_guidance(is_first_turn=False, **kwargs):
            del kwargs
            return {"context": guidance()} if is_first_turn else None
        ctx.register_hook("pre_llm_call", first_turn_guidance)


def _setup_cli(subparser):
    subs = subparser.add_subparsers(dest="librarian_command")
    setup = subs.add_parser("setup", help="Discover and configure the canonical knowledge root")
    setup.add_argument("--root", help="Existing knowledge directory to configure")
    setup.add_argument("--policy", choices=["strict", "balanced", "autonomous"], default="balanced")
    setup.add_argument("--non-interactive", action="store_true", help="Print candidates and exit without prompting")
    subs.add_parser("doctor", help="Run deterministic deployment diagnostics")
    subs.add_parser("status", help="Show current Librarian configuration")


def _setup_candidates():
    candidates = []
    seen = set()
    for label, raw in (("OBSIDIAN_VAULT_PATH", os.environ.get("OBSIDIAN_VAULT_PATH")),
                       ("WIKI_PATH", os.environ.get("WIKI_PATH")),
                       ("~/wiki", str(Path.home() / "wiki"))):
        if not raw:
            continue
        path = Path(os.path.expandvars(raw)).expanduser().resolve(strict=False)
        key = str(path).casefold()
        if path.is_dir() and key not in seen:
            seen.add(key)
            candidates.append({"label": label, "path": str(path), "obsidian": (path / ".obsidian").is_dir()})
    return candidates


def _handle_cli(ctx, args):
    command = getattr(args, "librarian_command", None)
    config = load_config(ctx)
    if command == "status":
        print(service.status(config, {}))
        return
    if command == "doctor":
        print(service.doctor(config, {}))
        return
    if command != "setup":
        print("Usage: hermes agentic-librarian <setup|doctor|status>")
        return

    requested = getattr(args, "root", None)
    candidates = _setup_candidates()
    if requested:
        selected = Path(requested).expanduser().resolve(strict=False)
        if not selected.is_dir():
            print(json.dumps({"status": "error", "message": f"Knowledge root is not an existing directory: {selected}"}))
            return
    elif len(candidates) == 1:
        selected = Path(candidates[0]["path"])
    elif getattr(args, "non_interactive", False) or not getattr(__import__("sys"), "stdin").isatty():
        print(json.dumps({"status": "needs_selection", "candidates": candidates, "message": "Run setup again with --root PATH."}, ensure_ascii=False))
        return
    else:
        print("Detected knowledge roots:")
        for index, item in enumerate(candidates, 1):
            suffix = " (Obsidian)" if item["obsidian"] else ""
            print(f"  {index}. {item['path']}{suffix}")
        if not candidates:
            print("  No existing root detected.")
        answer = input("Choose a number, or enter an existing path: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(candidates):
            selected = Path(candidates[int(answer) - 1]["path"])
        else:
            selected = Path(answer).expanduser().resolve(strict=False)
        if not selected.is_dir():
            print(json.dumps({"status": "error", "message": f"Knowledge root is not an existing directory: {selected}"}))
            return

    if not has_settings_bridge(ctx):
        print(json.dumps({"status": "unsupported_host", "message": "This Hermes host does not expose the native plugin settings bridge. Upgrade Hermes before running setup."}))
        return
    ctx.set_config("knowledge_root", str(selected))
    ctx.set_config("policy_mode", getattr(args, "policy", "balanced"))
    print(json.dumps({"status": "configured", "knowledge_root": str(selected), "policy_mode": getattr(args, "policy", "balanced")}, ensure_ascii=False))

def _register_commands(ctx):
    def librarian_command(raw_args: str) -> str:
        parts = raw_args.strip().split()
        action = parts[0].lower() if parts else "status"
        config = load_config(ctx)
        if action == "status":
            return service.status(config, {})
        if action == "doctor":
            return service.doctor(config, {})
        if action in {"review", "queue", "pending"}:
            return service.review_queue(config, {"limit": 20})
        if action == "history":
            return service.history(config, {"limit": 10})
        if action == "help":
            return (
                "Agentic Librarian commands:\n"
                "/librarian status   - integration and policy health\n"
                "/librarian review   - pending proposals\n"
                "/librarian history  - recent applied transactions\n"
                "For setup, ask Hermes to configure Agentic Librarian; configuration changes use the native approval gate."
            )
        return "Unknown action. Use /librarian help."

    if hasattr(ctx, "register_cli_command"):
        ctx.register_cli_command(
            name="agentic-librarian",
            help="Set up and diagnose Agentic Librarian",
            setup_fn=_setup_cli,
            handler_fn=lambda args: _handle_cli(ctx, args),
        )

    ctx.register_command(
        "librarian",
        handler=librarian_command,
        description="Status, review queue, and history for Agentic Librarian",
        args_hint="[status|doctor|review|history|help]",
    )


def _register_skill(ctx):
    skill_path = Path(__file__).parent / "skills" / "librarian" / "SKILL.md"
    if skill_path.exists():
        ctx.register_skill("librarian", skill_path)


def register(ctx):
    """Register tools, policy hooks, slash command, prompt guidance, and skill."""
    _register_tools(ctx)
    _register_hooks(ctx)
    _register_guidance(ctx)
    _register_commands(ctx)
    _register_skill(ctx)
    logger.info("Agentic Librarian registered")
