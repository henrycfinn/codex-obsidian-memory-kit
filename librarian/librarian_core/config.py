"""Configuration loading and root discovery.

The plugin intentionally uses only stdlib types. Hermes owns persistence of plugin
settings; this module simply reads the plugin-scoped values through PluginContext.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LibrarianConfig:
    knowledge_root: Path | None
    policy_mode: str = "balanced"
    enforce_direct_writes: bool = True
    guard_terminal_writes: bool = True
    governed_extensions: tuple[str, ...] = (".md", ".mdx", ".txt", ".rst", ".org")
    excluded_patterns: tuple[str, ...] = (".obsidian/**", ".git/**", ".trash/**", ".Trash/**")
    raw_patterns: tuple[str, ...] = ("raw/**", "sources/**", "Sources/**")
    human_controlled_patterns: tuple[str, ...] = (
        "SCHEMA.md",
        "**/SCHEMA.md",
        "AGENTS.md",
        "**/AGENTS.md",
        "HERMES.md",
        "**/HERMES.md",
        ".hermes.md",
        "**/.hermes.md",
    )
    major_rewrite_ratio: float = 0.35
    removal_review_ratio: float = 0.15
    max_auto_changes: int = 20
    qmd_duplicate_check: bool = True
    qmd_sync: str = "off"
    git_checkpoint: bool = False
    prompt_guidance: bool = True


def get_setting(ctx: Any, key: str, default: Any = None) -> Any:
    """Read settings on current and legacy Hermes plugin contexts."""
    getter = getattr(ctx, "get_config", None)
    if callable(getter):
        return getter(key, default=default)
    return default


def has_settings_bridge(ctx: Any) -> bool:
    return callable(getattr(ctx, "get_config", None)) and callable(getattr(ctx, "set_config", None))


def _list_value(ctx: Any, key: str, default: list[str]) -> tuple[str, ...]:
    value = get_setting(ctx, key, default=default)
    if not isinstance(value, list):
        return tuple(default)
    return tuple(str(item) for item in value if isinstance(item, (str, int, float)))


def discover_knowledge_root(explicit: str | None = None) -> Path | None:
    """Resolve the canonical knowledge root without inventing a directory.

    Order: explicit plugin setting -> OBSIDIAN_VAULT_PATH -> WIKI_PATH -> existing ~/wiki.
    Returning None is deliberate: governance should not silently protect the current
    working directory when the user has not identified a knowledge base.
    """

    candidates = [
        explicit or "",
        os.environ.get("OBSIDIAN_VAULT_PATH", ""),
        os.environ.get("WIKI_PATH", ""),
    ]
    for raw in candidates:
        raw = str(raw).strip()
        if not raw:
            continue
        path = Path(os.path.expandvars(raw)).expanduser()
        try:
            return path.resolve(strict=False)
        except OSError:
            return path.absolute()

    default = Path.home() / "wiki"
    if default.exists():
        return default.resolve(strict=False)
    return None


def load_config(ctx: Any) -> LibrarianConfig:
    explicit = str(get_setting(ctx, "knowledge_root", default="") or "")
    root = discover_knowledge_root(explicit)
    policy_mode = str(get_setting(ctx, "policy_mode", default="balanced") or "balanced").lower()
    if policy_mode not in {"strict", "balanced", "autonomous"}:
        policy_mode = "balanced"

    qmd_sync = str(get_setting(ctx, "qmd_sync", default="off") or "off").lower()
    if qmd_sync not in {"off", "update", "update_and_embed"}:
        qmd_sync = "off"

    governed = tuple(
        ext if str(ext).startswith(".") else f".{ext}"
        for ext in _list_value(ctx, "governed_extensions", [".md", ".mdx", ".txt", ".rst", ".org"])
    )

    def _float(key: str, default: float) -> float:
        try:
            return float(get_setting(ctx, key, default=default))
        except (TypeError, ValueError):
            return default

    def _int(key: str, default: int) -> int:
        try:
            return int(get_setting(ctx, key, default=default))
        except (TypeError, ValueError):
            return default

    return LibrarianConfig(
        knowledge_root=root,
        policy_mode=policy_mode,
        enforce_direct_writes=bool(get_setting(ctx, "enforce_direct_writes", default=True)),
        guard_terminal_writes=bool(get_setting(ctx, "guard_terminal_writes", default=True)),
        governed_extensions=governed,
        excluded_patterns=_list_value(ctx, "excluded_patterns", [".obsidian/**", ".git/**", ".trash/**", ".Trash/**"]),
        raw_patterns=_list_value(ctx, "raw_patterns", ["raw/**", "sources/**", "Sources/**"]),
        human_controlled_patterns=_list_value(
            ctx,
            "human_controlled_patterns",
            ["SCHEMA.md", "**/SCHEMA.md", "AGENTS.md", "**/AGENTS.md", "HERMES.md", "**/HERMES.md", ".hermes.md", "**/.hermes.md"],
        ),
        major_rewrite_ratio=max(0.0, min(1.0, _float("major_rewrite_ratio", 0.35))),
        removal_review_ratio=max(0.0, min(1.0, _float("removal_review_ratio", 0.15))),
        max_auto_changes=max(1, _int("max_auto_changes", 20)),
        qmd_duplicate_check=bool(get_setting(ctx, "qmd_duplicate_check", default=True)),
        qmd_sync=qmd_sync,
        git_checkpoint=bool(get_setting(ctx, "git_checkpoint", default=False)),
        prompt_guidance=bool(get_setting(ctx, "prompt_guidance", default=True)),
    )
