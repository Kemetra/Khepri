from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 2
REGISTRY_PATH = Path("governance/registry.yaml")
TOP_LEVEL_FIELDS = {"schema_version", "artifacts"}
ARTIFACT_FIELDS = {"type", "id", "state", "document", "depends_on"}
OPTIONAL_FIELDS = {"superseded_by"}
ARTIFACT_TYPES = {"decision", "family", "specification"}
ARTIFACT_STATES = {"active", "retired"}

Artifact = Mapping[str, Any]
ArtifactIndex = dict[str, Artifact]
FieldRules = tuple[set[str], set[str]]
VocabularyRule = tuple[str, set[str]]

REGISTRY_FIELD_RULES: FieldRules = (set(), TOP_LEVEL_FIELDS)
ARTIFACT_FIELD_RULES: FieldRules = (ARTIFACT_FIELDS, OPTIONAL_FIELDS)
TYPE_RULE: VocabularyRule = ("type", ARTIFACT_TYPES)
STATE_RULE: VocabularyRule = ("state", ARTIFACT_STATES)


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    artifacts = _load_artifacts(root, errors)
    if artifacts is None:
        return errors
    index = _validate_artifacts(root, artifacts, errors)
    _validate_dependencies(artifacts, index, errors)
    _validate_cycles(index, errors)
    _validate_family_links(artifacts, index, errors)
    _validate_supersession(artifacts, index, errors)
    return errors


def _load_artifacts(root: Path, errors: list[str]) -> list[Artifact] | None:
    loaded = _read_registry(root, errors)
    if loaded is None:
        return None
    return _extract_artifacts(loaded, errors)


def _read_registry(root: Path, errors: list[str]) -> object | None:
    path = root / REGISTRY_PATH
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"registry: file does not exist: {REGISTRY_PATH.as_posix()}")
        return None
    except (OSError, UnicodeError):
        errors.append(f"registry: cannot read: {REGISTRY_PATH.as_posix()}")
        return None
    except yaml.YAMLError:
        errors.append("registry: invalid YAML")
        return None


def _extract_artifacts(loaded: object, errors: list[str]) -> list[Artifact] | None:
    if not isinstance(loaded, dict):
        errors.append("registry: root must be a mapping")
        return None
    _report_field_errors("registry", loaded, REGISTRY_FIELD_RULES, errors)
    version = loaded.get("schema_version")
    if version != SCHEMA_VERSION:
        errors.append(f"registry: unsupported schema_version {version!r}".replace("None", "null"))
        return None
    artifacts = loaded.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("registry: artifacts must be a non-empty list")
        return None
    return _artifact_mappings(artifacts, errors)


def _artifact_mappings(artifacts: list[object], errors: list[str]) -> list[Artifact]:
    mappings: list[Artifact] = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            errors.append(f"registry: artifact[{index}] must be a mapping")
            continue
        mappings.append(artifact)
    return mappings


def _validate_artifacts(
    root: Path,
    artifacts: list[Artifact],
    errors: list[str],
) -> ArtifactIndex:
    return _ArtifactValidator(root, errors).validate(artifacts)


def _report_field_errors(
    label: str,
    item: Mapping[str, Any],
    rules: FieldRules,
    errors: list[str],
) -> None:
    required, optional = rules
    missing = sorted(required - item.keys())
    unknown = sorted(item.keys() - required - optional)
    if missing:
        errors.append(f"{label}: missing fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"{label}: unknown fields: {', '.join(unknown)}")


class _ArtifactValidator:
    def __init__(self, root: Path, errors: list[str]) -> None:
        self.root = root
        self.errors = errors
        self.index: ArtifactIndex = {}
        self.documents: set[str] = set()

    def validate(self, artifacts: list[Artifact]) -> ArtifactIndex:
        for position, artifact in enumerate(artifacts):
            self._validate_artifact(artifact, position)
        return self.index

    def _validate_artifact(self, artifact: Artifact, position: int) -> None:
        fallback = f"artifact[{position}]"
        artifact_id = artifact.get("id")
        label = artifact_id if _filled_text(artifact_id) else fallback
        _report_field_errors(
            f"registry: {fallback}", artifact, ARTIFACT_FIELD_RULES, self.errors
        )
        self._validate_values(label, fallback, artifact)
        self._record_identity(artifact_id, artifact)
        self._record_document(label, artifact.get("document"))

    def _validate_values(self, label: str, fallback: str, artifact: Artifact) -> None:
        if not _filled_text(artifact.get("id")):
            self.errors.append(f"registry: {fallback}: id must be a non-empty string")
        self._validate_vocabulary(label, artifact.get("type"), TYPE_RULE)
        self._validate_vocabulary(label, artifact.get("state"), STATE_RULE)
        dependencies = artifact.get("depends_on")
        if not _identifier_list(dependencies):
            self.errors.append(
                f"registry: {label}: depends_on must be a list of identifiers"
            )
        successor = artifact.get("superseded_by")
        if "superseded_by" in artifact and not _filled_text(successor):
            self.errors.append(
                f"registry: {label}: superseded_by must be a non-empty identifier"
            )

    def _validate_vocabulary(
        self,
        label: str,
        value: object,
        rule: VocabularyRule,
    ) -> None:
        field, allowed = rule
        if not isinstance(value, str):
            self.errors.append(f"registry: {label}: {field} must be a string")
        elif value not in allowed:
            self.errors.append(f"registry: {label}: unsupported {field} {value!r}")

    def _record_identity(self, artifact_id: object, artifact: Artifact) -> None:
        if not _filled_text(artifact_id):
            return
        if artifact_id in self.index:
            self.errors.append(f"registry: duplicate id {artifact_id!r}")
            return
        self.index[artifact_id] = artifact

    def _record_document(self, label: str, document: object) -> None:
        if not _filled_text(document):
            self.errors.append(f"registry: {label}: document must be a non-empty string")
            return
        path = Path(document)
        if path.is_absolute() or ".." in path.parts:
            self.errors.append(
                f"registry: {label}: document must be a repository-relative Markdown path"
            )
            return
        if path.suffix.lower() != ".md":
            self.errors.append(f"registry: {label}: document must be a Markdown file")
            return
        if document in self.documents:
            self.errors.append(f"registry: duplicate document {document!r}")
        self.documents.add(document)
        if not (self.root / path).is_file():
            self.errors.append(f"registry: {label}: document does not exist: {document}")


def _validate_dependencies(
    artifacts: list[Artifact],
    index: ArtifactIndex,
    errors: list[str],
) -> None:
    validator = _DependencyValidator(index, errors)
    for artifact in artifacts:
        validator.validate(artifact)


class _DependencyValidator:
    def __init__(self, index: ArtifactIndex, errors: list[str]) -> None:
        self.index = index
        self.errors = errors

    def validate(self, artifact: Artifact) -> None:
        artifact_id = artifact.get("id")
        dependencies = artifact.get("depends_on")
        if not _filled_text(artifact_id) or not _identifier_list(dependencies):
            return
        seen: set[str] = set()
        for dependency_id in dependencies:
            self._validate_dependency(artifact, dependency_id, seen)

    def _validate_dependency(
        self,
        artifact: Artifact,
        dependency_id: str,
        seen: set[str],
    ) -> None:
        artifact_id = artifact["id"]
        if dependency_id in seen:
            self.errors.append(
                f"registry: {artifact_id}: duplicate dependency {dependency_id!r}"
            )
        seen.add(dependency_id)
        if dependency_id == artifact_id:
            self.errors.append(f"registry: {artifact_id}: cannot depend on itself")
            return
        dependency = self.index.get(dependency_id)
        if dependency is None:
            self.errors.append(
                f"registry: {artifact_id}: unknown dependency {dependency_id!r}"
            )
            return
        if artifact.get("state") == "active" and dependency.get("state") == "retired":
            self.errors.append(
                f"registry: {artifact_id}: active artifact depends on retired artifact "
                f"{dependency_id!r}"
            )


def _validate_cycles(index: ArtifactIndex, errors: list[str]) -> None:
    graph = {
        artifact_id: _known_dependencies(artifact, index)
        for artifact_id, artifact in index.items()
    }
    cycle = _find_cycle(graph)
    if cycle:
        errors.append(f"registry: dependency cycle: {' -> '.join(cycle)}")


def _known_dependencies(artifact: Artifact, index: ArtifactIndex) -> list[str]:
    dependencies = artifact.get("depends_on")
    if not _identifier_list(dependencies):
        return []
    return [item for item in dependencies if item in index]


def _find_cycle(graph: Mapping[str, list[str]]) -> list[str]:
    return _CycleFinder(graph).find()


class _CycleFinder:
    def __init__(self, graph: Mapping[str, list[str]]) -> None:
        self.graph = graph
        self.visited: set[str] = set()
        self.stack: list[str] = []
        self.active: set[str] = set()

    def find(self) -> list[str]:
        for artifact_id in self.graph:
            cycle = self._visit(artifact_id)
            if cycle:
                return cycle
        return []

    def _visit(self, artifact_id: str) -> list[str]:
        if artifact_id in self.active:
            start = self.stack.index(artifact_id)
            return self.stack[start:] + [artifact_id]
        if artifact_id in self.visited:
            return []
        self.visited.add(artifact_id)
        self.active.add(artifact_id)
        self.stack.append(artifact_id)
        for dependency_id in self.graph.get(artifact_id, []):
            cycle = self._visit(dependency_id)
            if cycle:
                return cycle
        self.stack.pop()
        self.active.remove(artifact_id)
        return []


def _validate_family_links(
    artifacts: list[Artifact],
    index: ArtifactIndex,
    errors: list[str],
) -> None:
    for artifact in artifacts:
        if artifact.get("type") != "specification":
            continue
        artifact_id = artifact.get("id")
        dependencies = _known_dependencies(artifact, index)
        families = [item for item in dependencies if index[item].get("type") == "family"]
        if _filled_text(artifact_id) and len(families) != 1:
            errors.append(
                f"registry: {artifact_id}: specification must depend on exactly one family"
            )


def _validate_supersession(
    artifacts: list[Artifact],
    index: ArtifactIndex,
    errors: list[str],
) -> None:
    for artifact in artifacts:
        if "superseded_by" not in artifact:
            continue
        _validate_successor(artifact, index, errors)


def _validate_successor(
    artifact: Artifact,
    index: ArtifactIndex,
    errors: list[str],
) -> None:
    artifact_id = artifact.get("id")
    successor_id = artifact.get("superseded_by")
    if not _filled_text(artifact_id) or not _filled_text(successor_id):
        return
    if artifact.get("state") != "retired":
        errors.append(f"registry: {artifact_id}: only retired artifacts may name superseded_by")
        return
    if successor_id == artifact_id:
        errors.append(f"registry: {artifact_id}: cannot supersede itself")
        return
    successor = index.get(successor_id)
    if successor is None:
        errors.append(f"registry: {artifact_id}: unknown successor {successor_id!r}")
        return
    if successor.get("type") != artifact.get("type"):
        errors.append(
            f"registry: {artifact_id}: successor {successor_id!r} must have type "
            f"{artifact.get('type')!r}"
        )
    if successor.get("state") != "active":
        errors.append(f"registry: {artifact_id}: successor {successor_id!r} must be active")


def _identifier_list(value: object) -> bool:
    return isinstance(value, list) and all(_filled_text(item) for item in value)


def _filled_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
