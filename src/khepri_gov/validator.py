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


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    artifacts = _load_artifacts(root, errors)
    if artifacts is None:
        return errors
    index = _validate_artifacts(root, artifacts, errors)
    _validate_dependencies(artifacts, index, errors)
    _validate_cycles(artifacts, index, errors)
    _validate_family_links(artifacts, index, errors)
    _validate_supersession(artifacts, index, errors)
    return errors


def _load_artifacts(root: Path, errors: list[str]) -> list[Artifact] | None:
    path = root / REGISTRY_PATH
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"registry: file does not exist: {REGISTRY_PATH.as_posix()}")
        return None
    except (OSError, UnicodeError):
        errors.append(f"registry: cannot read: {REGISTRY_PATH.as_posix()}")
        return None
    except yaml.YAMLError:
        errors.append("registry: invalid YAML")
        return None
    if not isinstance(loaded, dict):
        errors.append("registry: root must be a mapping")
        return None
    _report_field_errors("registry", loaded, set(), TOP_LEVEL_FIELDS, errors)
    version = loaded.get("schema_version")
    if version != SCHEMA_VERSION:
        errors.append(f"registry: unsupported schema_version {version!r}".replace("None", "null"))
        return None
    artifacts = loaded.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("registry: artifacts must be a non-empty list")
        return None
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
    index: ArtifactIndex = {}
    documents: set[str] = set()
    for position, artifact in enumerate(artifacts):
        fallback = f"artifact[{position}]"
        artifact_id = artifact.get("id")
        label = artifact_id if _filled_text(artifact_id) else fallback
        _report_field_errors(
            f"registry: {fallback}", artifact, ARTIFACT_FIELDS, OPTIONAL_FIELDS, errors
        )
        _validate_values(label, fallback, artifact, errors)
        _record_identity(label, artifact_id, artifact, index, errors)
        _record_document(root, label, artifact.get("document"), documents, errors)
    return index


def _report_field_errors(
    label: str,
    item: Mapping[str, Any],
    required: set[str],
    optional: set[str],
    errors: list[str],
) -> None:
    missing = sorted(required - item.keys())
    unknown = sorted(item.keys() - required - optional)
    if missing:
        errors.append(f"{label}: missing fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"{label}: unknown fields: {', '.join(unknown)}")


def _validate_values(
    label: str,
    fallback: str,
    artifact: Artifact,
    errors: list[str],
) -> None:
    if not _filled_text(artifact.get("id")):
        errors.append(f"registry: {fallback}: id must be a non-empty string")
    _validate_vocabulary(label, "type", artifact.get("type"), ARTIFACT_TYPES, errors)
    _validate_vocabulary(label, "state", artifact.get("state"), ARTIFACT_STATES, errors)
    dependencies = artifact.get("depends_on")
    if not _identifier_list(dependencies):
        errors.append(f"registry: {label}: depends_on must be a list of identifiers")
    successor = artifact.get("superseded_by")
    if "superseded_by" in artifact and not _filled_text(successor):
        errors.append(f"registry: {label}: superseded_by must be a non-empty identifier")


def _validate_vocabulary(
    label: str,
    field: str,
    value: object,
    allowed: set[str],
    errors: list[str],
) -> None:
    if not isinstance(value, str):
        errors.append(f"registry: {label}: {field} must be a string")
    elif value not in allowed:
        errors.append(f"registry: {label}: unsupported {field} {value!r}")


def _record_identity(
    label: str,
    artifact_id: object,
    artifact: Artifact,
    index: ArtifactIndex,
    errors: list[str],
) -> None:
    if not _filled_text(artifact_id):
        return
    if artifact_id in index:
        errors.append(f"registry: duplicate id {artifact_id!r}")
        return
    index[artifact_id] = artifact


def _record_document(
    root: Path,
    label: str,
    document: object,
    documents: set[str],
    errors: list[str],
) -> None:
    if not _filled_text(document):
        errors.append(f"registry: {label}: document must be a non-empty string")
        return
    path = Path(document)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"registry: {label}: document must be a repository-relative Markdown path")
        return
    if path.suffix.lower() != ".md":
        errors.append(f"registry: {label}: document must be a Markdown file")
        return
    if document in documents:
        errors.append(f"registry: duplicate document {document!r}")
    documents.add(document)
    if not (root / path).is_file():
        errors.append(f"registry: {label}: document does not exist: {document}")


def _validate_dependencies(
    artifacts: list[Artifact],
    index: ArtifactIndex,
    errors: list[str],
) -> None:
    for artifact in artifacts:
        artifact_id = artifact.get("id")
        dependencies = artifact.get("depends_on")
        if not _filled_text(artifact_id) or not _identifier_list(dependencies):
            continue
        seen: set[str] = set()
        for dependency_id in dependencies:
            _validate_dependency(artifact, artifact_id, dependency_id, index, seen, errors)


def _validate_dependency(
    artifact: Artifact,
    artifact_id: str,
    dependency_id: str,
    index: ArtifactIndex,
    seen: set[str],
    errors: list[str],
) -> None:
    if dependency_id in seen:
        errors.append(f"registry: {artifact_id}: duplicate dependency {dependency_id!r}")
    seen.add(dependency_id)
    if dependency_id == artifact_id:
        errors.append(f"registry: {artifact_id}: cannot depend on itself")
        return
    dependency = index.get(dependency_id)
    if dependency is None:
        errors.append(f"registry: {artifact_id}: unknown dependency {dependency_id!r}")
        return
    if artifact.get("state") == "active" and dependency.get("state") == "retired":
        errors.append(
            f"registry: {artifact_id}: active artifact depends on retired artifact "
            f"{dependency_id!r}"
        )


def _validate_cycles(
    artifacts: list[Artifact],
    index: ArtifactIndex,
    errors: list[str],
) -> None:
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
    visited: set[str] = set()
    stack: list[str] = []
    active: set[str] = set()
    for artifact_id in graph:
        cycle = _visit(artifact_id, graph, visited, stack, active)
        if cycle:
            return cycle
    return []


def _visit(
    artifact_id: str,
    graph: Mapping[str, list[str]],
    visited: set[str],
    stack: list[str],
    active: set[str],
) -> list[str]:
    if artifact_id in active:
        start = stack.index(artifact_id)
        return stack[start:] + [artifact_id]
    if artifact_id in visited:
        return []
    visited.add(artifact_id)
    active.add(artifact_id)
    stack.append(artifact_id)
    for dependency_id in graph.get(artifact_id, []):
        cycle = _visit(dependency_id, graph, visited, stack, active)
        if cycle:
            return cycle
    stack.pop()
    active.remove(artifact_id)
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
