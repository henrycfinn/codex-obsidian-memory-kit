"""Local proposal and receipt storage.

Runtime data deliberately lives outside the knowledge root so search/index systems
such as QMD do not ingest unapproved proposals as if they were canonical knowledge.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import PLUGIN_ID
from .integrity import atomic_write_text


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def data_root() -> Path:
    """Return Hermes-managed durable plugin data when available.

    `plugin_data_dir` is the documented native-plugin storage helper. The fallback
    keeps the core testable/portable when imported outside a Hermes installation.
    """
    try:
        from plugins.plugin_storage import plugin_data_dir  # documented Hermes helper
        return plugin_data_dir(PLUGIN_ID)
    except Exception:
        hermes_home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
        root = hermes_home / "plugin-data" / PLUGIN_ID
        root.mkdir(parents=True, exist_ok=True)
        return root


def _safe_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}-{secrets.token_hex(3)}"


def _json_write(path: Path, data: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def proposal_sha256(payload: dict[str, Any]) -> str:
    """Hash the complete proposal envelope, excluding its self-referential hash."""
    import hashlib

    canonical = dict(payload)
    canonical.pop("proposal_sha256", None)
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_proposal(payload: dict[str, Any]) -> bool:
    expected = payload.get("proposal_sha256")
    return isinstance(expected, str) and expected == proposal_sha256(payload)


def create_proposal(payload: dict[str, Any]) -> tuple[str, Path]:
    proposal_id = _safe_id("proposal")
    payload = dict(payload)
    payload["proposal_id"] = proposal_id
    payload.setdefault("created_at", utc_now())
    payload.setdefault("status", "pending")
    payload["schema_version"] = int(payload.get("schema_version", 1))
    payload["proposal_sha256"] = proposal_sha256(payload)
    path = data_root() / "proposals" / "pending" / f"{proposal_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _json_write(path, payload)
    return proposal_id, path


def get_proposal(proposal_id: str, status: str = "pending") -> dict[str, Any] | None:
    if not proposal_id or "/" in proposal_id or "\\" in proposal_id or ".." in proposal_id:
        return None
    path = data_root() / "proposals" / status / f"{proposal_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_proposals(limit: int = 20, knowledge_root: str | None = None) -> list[dict[str, Any]]:
    folder = data_root() / "proposals" / "pending"
    if not folder.exists():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(folder.glob("proposal-*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if knowledge_root is not None and data.get("knowledge_root") != knowledge_root:
            continue
        entries.append(
            {
                "proposal_id": data.get("proposal_id"),
                "created_at": data.get("created_at"),
                "summary": data.get("summary", ""),
                "reasons": data.get("reasons", []),
                "paths": [c.get("path") for c in data.get("changes", []) if isinstance(c, dict)],
            }
        )
        if len(entries) >= max(1, limit):
            break
    return entries


def move_proposal(proposal_id: str, destination: str, extra: dict[str, Any] | None = None) -> bool:
    source = data_root() / "proposals" / "pending" / f"{proposal_id}.json"
    if not source.exists() or destination not in {"applied", "rejected", "stale"}:
        return False
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    payload["status"] = destination
    payload[f"{destination}_at"] = utc_now()
    if extra:
        payload.update(extra)
    target = data_root() / "proposals" / destination / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    _json_write(target, payload)
    source.unlink(missing_ok=True)
    return True


def write_receipt(payload: dict[str, Any]) -> tuple[str, Path]:
    transaction_id = str(payload.get("transaction_id") or _safe_id("tx"))
    payload = dict(payload)
    payload["transaction_id"] = transaction_id
    payload.setdefault("timestamp", utc_now())
    now = datetime.now(timezone.utc)
    path = data_root() / "receipts" / f"{now.year:04d}" / f"{now.month:02d}" / f"{transaction_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _json_write(path, payload)
    return transaction_id, path


def recent_receipts(limit: int = 10, knowledge_root: str | None = None) -> list[dict[str, Any]]:
    root = data_root() / "receipts"
    if not root.exists():
        return []
    files = sorted(root.glob("*/*/tx-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict[str, Any]] = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if knowledge_root is not None and data.get("knowledge_root") != knowledge_root:
            continue
        out.append(
            {
                "transaction_id": data.get("transaction_id"),
                "timestamp": data.get("timestamp"),
                "summary": data.get("summary", ""),
                "decision": data.get("decision", ""),
                "paths": [c.get("path") for c in data.get("changes", []) if isinstance(c, dict)],
                "git_commit": data.get("git_commit"),
                "qmd": data.get("qmd"),
            }
        )
        if len(out) >= max(1, limit):
            break
    return out
