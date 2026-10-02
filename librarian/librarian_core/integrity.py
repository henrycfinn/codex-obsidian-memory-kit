"""Hashing and atomic file mutation primitives."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


@contextmanager
def transaction_lock(root: Path, timeout_seconds: float = 15.0, stale_after_seconds: float = 600.0):
    """Best-effort cross-process lock keyed by the canonical knowledge root.

    The lock lives in the operating-system temp directory rather than the vault, so
    retrieval/index tools do not see it. O_EXCL makes acquisition atomic on normal
    local filesystems. This coordinates Librarian processes on one machine; it is
    not a distributed lock for network filesystems or multiple hosts.
    """

    root_key = sha256_text(str(root.resolve(strict=False)))
    lock_dir = Path(tempfile.gettempdir()) / "hermes-agentic-librarian-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{root_key}.lock"
    deadline = time.monotonic() + max(0.1, timeout_seconds)
    fd = None

    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > stale_after_seconds:
                    lock_path.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("Timed out waiting for another Librarian transaction on this knowledge root.")
            time.sleep(0.05)

    try:
        payload = {"pid": os.getpid(), "created": time.time()}
        os.write(fd, (json.dumps(payload) + "\n").encode("utf-8"))
        os.close(fd)
        fd = None
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass
