from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

PACKAGE_SCHEMA_VERSION = 1
PACKAGE_STATES = {"proposed", "approved"}
DIGEST_PREFIX = "sha256:"
MANIFEST_FIELDS = (
    "schema_version",
    "id",
    "title",
    "owner",
    "scope",
    "exclusions",
    "artifacts",
)


def _sha256(content: bytes) -> str:
    return f"{DIGEST_PREFIX}{hashlib.sha256(content).hexdigest()}"


def document_digest(path: Path) -> str:
    return _sha256(path.read_bytes())


def manifest_payload(package: Mapping[str, Any]) -> dict[str, Any]:
    return {field: package.get(field) for field in MANIFEST_FIELDS}


def manifest_digest(package: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        manifest_payload(package),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return _sha256(encoded)


def load_package(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None, [f"approval-packages:{path.name}: invalid YAML"]
    if not isinstance(loaded, dict):
        return None, [f"approval-packages:{path.name}: root must be a mapping"]
    return loaded, []
