"""Path containment, matching, and governed-file helpers."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterable


def normalize_for_match(relative: Path | str) -> str:
    return str(relative).replace(os.sep, "/").lstrip("./")


def matches_any(relative: Path | str, patterns: Iterable[str]) -> bool:
    value = normalize_for_match(relative)
    name = Path(value).name
    for pattern in patterns:
        p = str(pattern).replace("\\", "/")
        if fnmatch.fnmatchcase(value, p) or fnmatch.fnmatchcase(name, p):
            return True
        # pathlib-style **/foo does not match root-level foo in fnmatch on all versions.
        if p.startswith("**/") and fnmatch.fnmatchcase(value, p[3:]):
            return True
    return False


def resolve_inside(root: Path, requested: str | Path) -> tuple[Path, Path]:
    """Resolve a user/model supplied path and guarantee it stays within root.

    Existing symlinks are resolved, so a symlink in the vault cannot escape containment.
    For a not-yet-existing file, the nearest existing parent is resolved first.
    """

    requested_path = Path(os.path.expandvars(str(requested))).expanduser()
    candidate = requested_path if requested_path.is_absolute() else root / requested_path
    root_real = root.resolve(strict=False)

    # Resolve the nearest existing ancestor to catch symlink escapes even for new files.
    ancestor = candidate
    suffix: list[str] = []
    while not ancestor.exists() and ancestor != ancestor.parent:
        suffix.append(ancestor.name)
        ancestor = ancestor.parent
    try:
        resolved_ancestor = ancestor.resolve(strict=True) if ancestor.exists() else ancestor.resolve(strict=False)
    except OSError:
        resolved_ancestor = ancestor.absolute()
    resolved = resolved_ancestor
    for part in reversed(suffix):
        resolved = resolved / part
    resolved = resolved.resolve(strict=False)

    try:
        relative = resolved.relative_to(root_real)
    except ValueError as exc:
        raise ValueError(f"Path escapes knowledge root: {requested}") from exc
    return resolved, relative


def is_governed(relative: Path, extensions: tuple[str, ...], excluded_patterns: tuple[str, ...]) -> bool:
    if matches_any(relative, excluded_patterns):
        return False
    return relative.suffix.lower() in {ext.lower() for ext in extensions}
