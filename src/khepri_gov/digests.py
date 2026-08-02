from __future__ import annotations

import hashlib
from pathlib import Path

DIGEST_PREFIX = "sha256:"


def content_digest(content: bytes) -> str:
    return f"{DIGEST_PREFIX}{hashlib.sha256(content).hexdigest()}"


def document_digest(path: Path) -> str:
    return content_digest(path.read_bytes())
