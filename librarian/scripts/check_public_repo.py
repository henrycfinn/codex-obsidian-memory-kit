#!/usr/bin/env python3
"""Fail CI on common accidental private/secret material in the public source tree.

This intentionally avoids embedding any maintainer-specific identifiers. It is a
lightweight hygiene check, not a replacement for a dedicated secret scanner.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "dist", "build"}
SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".gz", ".tar", ".pdf"}

CHECKS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Windows user home": re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+\\"),
    "macOS user home": re.compile(r"/Users/(?!user(?:/|\b)|example(?:/|\b)|<)[^/\s]+/"),
    "Linux user home": re.compile(r"/home/(?!user(?:/|\b)|example(?:/|\b)|<)[^/\s]+/"),
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@(?!example\.com\b)[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
}

FORBIDDEN_RUNTIME_PARTS = {"plugin-data", "proposals", "receipts"}


def text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts) or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        yield path, rel


def main() -> int:
    problems = []
    for path, rel in text_files():
        # Runtime dirs are forbidden unless the path is documentation/source text referring to them.
        if rel.parts and rel.parts[0] in FORBIDDEN_RUNTIME_PARTS:
            problems.append((str(rel), "runtime state directory"))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in CHECKS.items():
            # The scanner necessarily contains its own home-path detector patterns.
            if rel.as_posix() == "scripts/check_public_repo.py" and label in {"Windows user home", "macOS user home", "Linux user home"}:
                continue
            if pattern.search(text):
                problems.append((str(rel), label))

    # Sensitive dotfiles should not ship even if empty.
    for name in (".env", ".env.local", "credentials.json", "secrets.json"):
        if (ROOT / name).exists():
            problems.append((name, "sensitive local configuration"))

    if problems:
        print("Public repository hygiene check FAILED:")
        for rel, label in sorted(set(problems)):
            print(f"  - {rel}: {label}")
        return 1
    print("Public repository hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
