from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from khepri_gov.approval_packages import document_digest, manifest_digest


def example_package() -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": "APP-002",
        "title": "Example",
        "state": "proposed",
        "owner": "AHMED-SHAABAN",
        "scope": "Approve exact artifacts.",
        "exclusions": ["Product code"],
        "manifest_digest": "sha256:" + ("0" * 64),
        "artifacts": [
            {
                "id": "KHEPRI-DEC-002",
                "document": "governance/decisions/KHEPRI-DEC-002.md",
                "document_sha256": "sha256:" + ("a" * 64),
                "from_state": "proposed",
                "to_state": "accepted",
            }
        ],
    }


def test_manifest_digest_is_canonical_and_excludes_approval_state() -> None:
    package = example_package()

    assert manifest_digest(package) == (
        "sha256:796d415bf26999eb891b4af35f1b4f49f814abb4ed83a1320e5f646fb0ac0f07"
    )

    approved = deepcopy(package)
    approved["state"] = "approved"
    approved["approval"] = {
        "approved_by": "AHMED-SHAABAN",
        "approved_at": "2026-07-29",
        "approved_manifest_digest": manifest_digest(package),
        "evidence_ref": (
            "https://github.com/Kemetra/Khepri/pull/4"
            "#issuecomment-0000000000"
        ),
    }
    assert manifest_digest(approved) == manifest_digest(package)


def test_document_digest_hashes_exact_utf8_bytes(tmp_path: Path) -> None:
    document = tmp_path / "decision.md"
    document.write_bytes(b"# KHEPRI-DEC-002\n")

    assert document_digest(document) == (
        "sha256:9b08cd92ee3f228e9d7167a935ec8acf13567019c633471fa6dab2bc1f5790ef"
    )
