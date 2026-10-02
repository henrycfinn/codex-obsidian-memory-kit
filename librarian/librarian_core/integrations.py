"""Optional integrations: Obsidian detection, QMD lookup/sync, and Git checkpoints."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .paths import matches_any, normalize_for_match


def detect_obsidian(root: Path | None) -> bool:
    return bool(root and (root / ".obsidian").is_dir())


def _qmd_command() -> str | None:
    """Resolve QMD to an executable Windows can launch via subprocess."""
    candidates = ["qmd.cmd", "qmd.exe", "qmd"] if os.name == "nt" else ["qmd"]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _qmd_args(*args: str) -> list[str]:
    return [_qmd_command() or "qmd", *args]


def qmd_available() -> bool:
    return _qmd_command() is not None


def git_available() -> bool:
    return shutil.which("git") is not None


def _spawn_args(args: list[str]) -> list[str]:
    """Return executable arguments that also work with Windows batch shims.

    npm exposes command-line packages as ``.cmd`` launchers.  ``shutil.which``
    finds those launchers, but ``subprocess.run(..., shell=False)`` cannot
    reliably execute them directly.  Run only a resolved batch launcher via
    ``cmd.exe``; native executables retain the safer direct invocation.
    """
    if os.name != "nt" or not args:
        return args
    executable = shutil.which(args[0])
    if not executable or Path(executable).suffix.lower() not in {".cmd", ".bat"}:
        return args
    command = subprocess.list2cmdline([executable, *args[1:]])
    return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command]


def _run(args: list[str], cwd: Path | None = None, timeout: int = 60) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            _spawn_args(args),
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=os.environ.copy(),
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


def qmd_status() -> dict[str, Any]:
    if not qmd_available():
        return {"available": False}
    code, out, err = _run(_qmd_args("status"), timeout=20)
    return {
        "available": True,
        "ok": code == 0,
        "summary": (out or err)[:2000],
    }


def _extract_qmd_paths(payload: Any, root: Path) -> list[Path]:
    """Extract result paths from several QMD JSON shapes without binding to one release."""
    rows: list[Any]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = []
        for key in ("results", "matches", "documents", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break
        if not rows:
            rows = [payload]
    else:
        return []

    found: list[Path] = []
    root_real = root.resolve(strict=False)
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = None
        for key in ("path", "file", "full_path", "filepath", "displayPath", "display_path"):
            value = row.get(key)
            if isinstance(value, str) and value:
                raw = value
                break
        if not raw:
            continue
        if raw.startswith("qmd://"):
            continue
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = (root / candidate).resolve(strict=False)
        else:
            candidate = candidate.resolve(strict=False)
        try:
            candidate.relative_to(root_real)
        except ValueError:
            continue
        found.append(candidate)
    return found


def qmd_duplicate_candidates(root: Path, relative: Path, title_hint: str = "") -> list[str]:
    """Use QMD's read-only BM25 search to find strong name/title duplicates.

    The plugin intentionally does not invoke model-backed qmd query here. This keeps
    preflight quick and avoids loading local models simply because a page is created.
    """
    if not qmd_available():
        return []
    query = title_hint.strip() or relative.stem.replace("-", " ").replace("_", " ")
    if len(query) < 3:
        return []
    code, out, _ = _run(
        _qmd_args("search", query, "--format", "json", "--full-path", "-n", "8"),
        cwd=root,
        timeout=15,
    )
    if code != 0 or not out:
        return []
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return []

    target_stem = relative.stem.lower().replace("-", " ").replace("_", " ")
    candidates: list[str] = []
    for path in _extract_qmd_paths(payload, root):
        try:
            rel = path.relative_to(root.resolve(strict=False))
        except ValueError:
            continue
        if rel == relative:
            continue
        stem = rel.stem.lower().replace("-", " ").replace("_", " ")
        score = SequenceMatcher(a=target_stem, b=stem, autojunk=False).ratio()
        if score >= 0.88:
            candidates.append(rel.as_posix())
    return list(dict.fromkeys(candidates))[:5]


def filesystem_duplicate_candidates(
    root: Path, relative: Path, limit: int = 2500, excluded_patterns: tuple[str, ...] = ()
) -> list[str]:
    """Dependency-free filename similarity fallback for new notes."""
    target = relative.stem.lower().replace("-", " ").replace("_", " ")
    if not target:
        return []
    results: list[tuple[float, str]] = []
    count = 0
    for path in root.rglob("*.md"):
        count += 1
        if count > limit:
            break
        try:
            rel = path.resolve(strict=False).relative_to(root.resolve(strict=False))
        except ValueError:
            continue
        if rel == relative or any(part in {".git", ".obsidian"} for part in rel.parts):
            continue
        if excluded_patterns and matches_any(rel, excluded_patterns):
            continue
        stem = rel.stem.lower().replace("-", " ").replace("_", " ")
        score = SequenceMatcher(a=target, b=stem, autojunk=False).ratio()
        if score >= 0.92:
            results.append((score, normalize_for_match(rel)))
    results.sort(reverse=True)
    return [path for _, path in results[:5]]


def sync_qmd(mode: str, root: Path) -> dict[str, Any]:
    if mode == "off":
        return {"mode": "off", "attempted": False}
    if not qmd_available():
        return {"mode": mode, "attempted": False, "available": False}

    result: dict[str, Any] = {"mode": mode, "attempted": True, "available": True}
    code, out, err = _run(_qmd_args("update"), cwd=root, timeout=120)
    result["update_ok"] = code == 0
    result["update_message"] = (out or err)[-1200:]
    if code != 0 or mode != "update_and_embed":
        return result

    code, out, err = _run(_qmd_args("embed"), cwd=root, timeout=300)
    result["embed_ok"] = code == 0
    result["embed_message"] = (out or err)[-1200:]
    return result


def git_repo_root(root: Path) -> Path | None:
    if not git_available():
        return None
    code, out, _ = _run(["git", "rev-parse", "--show-toplevel"], cwd=root, timeout=10)
    if code != 0 or not out:
        return None
    return Path(out).resolve(strict=False)


def git_is_clean(root: Path) -> tuple[Path | None, bool]:
    repo = git_repo_root(root)
    if repo is None:
        return None, False
    code, out, _ = _run(["git", "status", "--porcelain"], cwd=repo, timeout=10)
    return repo, code == 0 and not out.strip()


def git_commit_paths(repo: Path, root: Path, relative_paths: list[str], message: str) -> dict[str, Any]:
    paths: list[str] = []
    for relative in relative_paths:
        absolute = (root / relative).resolve(strict=False)
        try:
            repo_rel = absolute.relative_to(repo)
        except ValueError:
            return {"attempted": False, "reason": "knowledge_root_outside_repo"}
        paths.append(repo_rel.as_posix())

    code, _, err = _run(["git", "add", "--", *paths], cwd=repo, timeout=20)
    if code != 0:
        return {"attempted": True, "ok": False, "reason": "git_add_failed", "message": err}
    clean_message = " ".join(message.strip().split())[:72] or "knowledge update"
    code, out, err = _run(["git", "commit", "-m", f"librarian: {clean_message}"], cwd=repo, timeout=30)
    if code != 0:
        _run(["git", "reset", "HEAD", "--", *paths], cwd=repo, timeout=10)
        return {"attempted": True, "ok": False, "reason": "git_commit_failed", "message": (out or err)[-1200:]}
    code, sha, _ = _run(["git", "rev-parse", "HEAD"], cwd=repo, timeout=10)
    return {"attempted": True, "ok": code == 0, "commit": sha.strip() if code == 0 else None}
