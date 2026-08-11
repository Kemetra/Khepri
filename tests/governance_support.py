from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def valid_artifacts() -> list[dict[str, Any]]:
    return [
        {
            "type": "family",
            "id": "FND",
            "state": "active",
            "document": "governance/families/FND.md",
            "depends_on": [],
        },
        {
            "type": "specification",
            "id": "FND-001",
            "state": "active",
            "document": "governance/specifications/FND-001.md",
            "depends_on": ["FND"],
        },
    ]


def decision(
    artifact_id: str = "KHEPRI-DEC-001",
    *,
    state: str = "active",
) -> dict[str, Any]:
    return {
        "type": "decision",
        "id": artifact_id,
        "state": state,
        "document": f"governance/decisions/{artifact_id}.md",
        "depends_on": [],
    }


def write_registry(root: Path, artifacts: list[dict[str, Any]]) -> None:
    registry = root / "governance" / "registry.yaml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        yaml.safe_dump({"schema_version": 2, "artifacts": artifacts}, sort_keys=False),
        encoding="utf-8",
    )
    for artifact in artifacts:
        document = artifact.get("document")
        if not _safe_document(document):
            continue
        path = root / document
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {artifact.get('id', 'artifact')}\n", encoding="utf-8")


def write_raw_registry(root: Path, content: str) -> None:
    registry = root / "governance" / "registry.yaml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(content, encoding="utf-8")


def _safe_document(document: object) -> bool:
    if not isinstance(document, str):
        return False
    path = Path(document)
    return not path.is_absolute() and ".." not in path.parts
