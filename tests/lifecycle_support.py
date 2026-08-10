from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from khepri_gov.approval_packages import document_digest, manifest_digest
from tests.test_cli import read_yaml, valid_repository, write_document, write_yaml

REGISTRIES = ("decisions", "families", "specifications")
INITIAL_STATES = {
    "decisions": ("proposed", "accepted"),
    "families": ("proposed", "active"),
    "specifications": ("draft", "approved"),
}


@dataclass(frozen=True)
class Transition:
    artifact_id: str
    to_state: str
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class LifecycleRepo:
    root: Path

    @classmethod
    def create(cls, root: Path) -> LifecycleRepo:
        valid_repository(root)
        fixture = cls(root)
        fixture._add_initial_graph()
        return fixture

    def artifact(self, artifact_id: str) -> tuple[str, dict[str, object]]:
        for registry in REGISTRIES:
            data = read_yaml(self._registry_path(registry))
            collection = data[registry]
            assert isinstance(collection, list)
            for artifact in collection:
                if artifact["id"] == artifact_id:
                    return registry, artifact
        raise AssertionError(f"unknown fixture artifact {artifact_id}")

    def propose(
        self,
        package_id: str,
        transition: Transition,
    ) -> tuple[Path, dict[str, object]]:
        _, artifact = self.artifact(transition.artifact_id)
        entry = self._transition_entry(
            artifact,
            transition.to_state,
            **transition.extra,
        )
        package = self._package(package_id, [entry])
        path = self.root / "governance/approvals" / f"{package_id}.yaml"
        write_yaml(path, package)
        return path, package

    def approve(self, path: Path, package: dict[str, object]) -> None:
        package["state"] = "approved"
        package["approval"] = self._approval(package)
        write_yaml(path, package)
        entries = package["artifacts"]
        assert isinstance(entries, list)
        for entry in entries:
            assert isinstance(entry, dict)
            self._materialize(path, entry)

    @staticmethod
    def rewrite(path: Path, package: dict[str, object]) -> None:
        package["manifest_digest"] = manifest_digest(package)
        write_yaml(path, package)

    @staticmethod
    def entry(package: dict[str, object]) -> dict[str, object]:
        entries = package["artifacts"]
        assert isinstance(entries, list)
        entry = entries[0]
        assert isinstance(entry, dict)
        return entry

    def decision_supersession(
        self,
        reverse: bool = False,
    ) -> tuple[Path, dict[str, object]]:
        successor = self._add_successor_decision()
        _, prior = self.artifact("KHEPRI-DEC-002")
        entries = [
            self._initial_entry(successor, "accepted"),
            {
                **self._transition_entry(prior, "superseded"),
                "superseded_by": "KHEPRI-DEC-003",
            },
        ]
        if reverse:
            entries.reverse()
        package = self._package("APP-003", entries)
        path = self.root / "governance/approvals/APP-003.yaml"
        write_yaml(path, package)
        return path, package

    def _add_initial_graph(self) -> None:
        additions = self._initial_artifacts()
        entries: list[dict[str, object]] = []
        for registry, artifact in additions:
            data = read_yaml(self._registry_path(registry))
            collection = data[registry]
            assert isinstance(collection, list)
            collection.append(artifact)
            write_yaml(self._registry_path(registry), data)
            entries.append(self._initial_entry(artifact, INITIAL_STATES[registry][1]))
        package = self._package("APP-002", entries)
        package["state"] = "approved"
        package["approval"] = self._approval(package, "2026-07-29")
        path = self.root / "governance/approvals/APP-002.yaml"
        write_yaml(path, package)
        for entry in entries:
            self._materialize(path, entry, "2026-07-29")

    def _materialize(
        self,
        path: Path,
        entry: dict[str, object],
        approved_at: str = "2026-07-30",
    ) -> None:
        registry, artifact = self.artifact(str(entry["id"]))
        data = read_yaml(self._registry_path(registry))
        collection = data[registry]
        assert isinstance(collection, list)
        current = next(item for item in collection if item["id"] == artifact["id"])
        current["state"] = entry["to_state"]
        if entry["to_state"] not in {"retired", "superseded"}:
            current.update(
                approved_by="AHMED-SHAABAN",
                approved_at=approved_at,
                approval_ref=path.relative_to(self.root).as_posix(),
            )
        if entry["to_state"] == "superseded":
            current["superseded_by"] = entry["superseded_by"]
        write_yaml(self._registry_path(registry), data)

    def _add_successor_decision(self) -> dict[str, object]:
        document = "governance/decisions/KHEPRI-DEC-003.md"
        write_document(self.root, document)
        data = read_yaml(self._registry_path("decisions"))
        decisions = data["decisions"]
        assert isinstance(decisions, list)
        successor: dict[str, object] = {
            "id": "KHEPRI-DEC-003",
            "title": "Superseding decision",
            "consequence": "none",
            "state": "proposed",
            "owner": "AHMED-SHAABAN",
            "document": document,
        }
        decisions.append(successor)
        write_yaml(self._registry_path("decisions"), data)
        return successor

    def _entry(
        self,
        artifact: dict[str, object],
        from_state: object,
        to_state: str,
    ) -> dict[str, object]:
        document = str(artifact["document"])
        return {
            "id": artifact["id"],
            "document": document,
            "document_sha256": document_digest(self.root / document),
            "from_state": from_state,
            "to_state": to_state,
        }

    def _initial_entry(
        self,
        artifact: dict[str, object],
        to_state: str,
    ) -> dict[str, object]:
        document = str(artifact["document"])
        registry = next(name for name in REGISTRIES if name in document)
        return self._entry(artifact, INITIAL_STATES[registry][0], to_state)

    def _transition_entry(
        self,
        artifact: dict[str, object],
        to_state: str,
        **extra: object,
    ) -> dict[str, object]:
        return {
            **self._entry(artifact, artifact["state"], to_state),
            "supersedes_approval_ref": artifact["approval_ref"],
            **extra,
        }

    @staticmethod
    def _package(
        package_id: str,
        entries: list[dict[str, object]],
    ) -> dict[str, object]:
        package: dict[str, object] = {
            "schema_version": 1,
            "id": package_id,
            "title": f"Lifecycle package {package_id}",
            "state": "proposed",
            "owner": "AHMED-SHAABAN",
            "scope": "Exercise governed lifecycle transitions.",
            "exclusions": ["Product application code"],
            "artifacts": entries,
        }
        package["manifest_digest"] = manifest_digest(package)
        return package

    @staticmethod
    def _approval(
        package: dict[str, object],
        approved_at: str = "2026-07-30",
    ) -> dict[str, object]:
        return {
            "approved_by": "AHMED-SHAABAN",
            "approved_at": approved_at,
            "approved_manifest_digest": package["manifest_digest"],
            "evidence_ref": (
                "https://github.com/Kemetra/Khepri/issues/2"
                "#issuecomment-0000000002"
            ),
        }

    def _registry_path(self, registry: str) -> Path:
        return self.root / "governance/registries" / f"{registry}.yaml"

    def _initial_artifacts(self) -> tuple[tuple[str, dict[str, object]], ...]:
        artifacts = (
            (
                "decisions",
                {
                    "id": "KHEPRI-DEC-002",
                    "title": "Lifecycle decision",
                    "consequence": "none",
                    "state": "proposed",
                    "owner": "AHMED-SHAABAN",
                    "document": "governance/decisions/KHEPRI-DEC-002.md",
                },
            ),
            (
                "families",
                {
                    "id": "AUX",
                    "name": "Auxiliary family",
                    "state": "proposed",
                    "owner": "AHMED-SHAABAN",
                    "document": "governance/families/AUX.md",
                    "depends_on": [],
                },
            ),
            (
                "specifications",
                {
                    "id": "FND-002",
                    "title": "Lifecycle specification",
                    "consequence": "none",
                    "state": "draft",
                    "family": "FND",
                    "owner": "AHMED-SHAABAN",
                    "document": "governance/specifications/FND-002.md",
                    "depends_on": ["FND-001"],
                },
            ),
        )
        for _, artifact in artifacts:
            write_document(self.root, str(artifact["document"]))
        return artifacts
