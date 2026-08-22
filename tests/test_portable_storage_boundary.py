"""The active storage path names no cloud provider. `KHEPRI-DEC-008`, structurally.

**Why a scan and not a review.** Every other test here proves a behaviour. This one
proves an absence, which behaviour cannot: a reintroduced `ExpectedBucketOwner` would
break a stub-matched test in `test_rra002_s3_storage.py`, but a reintroduced
`me-central-1` default, a KMS ARN regex, or an `if provider == "aws"` branch would
break nothing and pass review twice.

**What is in scope, and what deliberately is not.** The scan covers the layers where
neutrality is actually required: `khepri.rra`, `khepri.runtime`, `khepri.local`, and
`migrations`. It excludes `khepri.infra`, which `KHEPRI-DEC-008` freezes as the worked
example of the *retired* AWS task definition -- rewriting it to satisfy a grep would
destroy the only record of that reasoning. It also excludes this file and the tests,
which must be free to name the retired values in order to assert they are gone.

**Why the haystack is asserted.** A scan that walks an empty file list reports success.
A path typo, a renamed package, or a changed layout would silently disarm every
assertion below, so the file count and the presence of a known marker are checked
first. This is the failure mode a scan scoped to one place always has.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The layers that must be provider-neutral.
SCANNED_ROOTS = (
    REPO_ROOT / "src" / "khepri" / "rra",
    REPO_ROOT / "src" / "khepri" / "runtime",
    REPO_ROOT / "src" / "khepri" / "local",
    REPO_ROOT / "migrations",
)

# Frozen by `KHEPRI-DEC-008` and closed to new slices. Not scanned by design.
EXCLUDED = REPO_ROOT / "src" / "khepri" / "infra"

# Values that would mean the AWS-specific storage model had returned. Checked against
# *executable* string constants and identifiers rather than raw file text, so a
# docstring explaining what was removed does not trip them -- which is what lets the
# modules keep their history without weakening the guard.
FORBIDDEN_LITERALS = (
    "aws:kms",
    "me-central-1",
    "SSEKMSKeyId",
    "SSEKMSEncryptionContext",
    "BucketKeyEnabled",
    "ExpectedBucketOwner",
    "ServerSideEncryption",
    "KHEPRI_AWS_REGION",
    "KHEPRI_KMS_KEY_ARN",
    "KHEPRI_EXPECTED_BUCKET_OWNER",
)

# Names that would mean provider identity had become application behaviour.
FORBIDDEN_NAMES = ("kms_key_arn", "kms_key_id", "expected_bucket_owner")

# Provider names that must not become application behaviour. `localstack` is
# deliberately absent: `khepri.local.wiring.LocalStack` is this repository's own
# local-development composition root, and a substring match on it would flag a class
# that names no cloud provider at all. The emulator is reached through a configured
# endpoint like any other store, so its name has nowhere to appear.
PROVIDER_NAMES = ("digitalocean", "hetzner", "minio", "spaces")


def scanned_files() -> tuple[Path, ...]:
    found: list[Path] = []
    for root in SCANNED_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if EXCLUDED in path.parents:
                continue
            found.append(path)
    return tuple(found)


_SCOPES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _docstring_node(scope: ast.AST) -> ast.Constant | None:
    """The scope's docstring constant, if its first statement is one."""
    body = getattr(scope, "body", None)
    if not body:
        return None
    first = body[0]
    if not isinstance(first, ast.Expr):
        return None
    value = first.value
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value
    return None


def docstrings(tree: ast.AST) -> set[int]:
    """The id() of every docstring node, so prose can be told from a value.

    A module that explains which AWS field it stopped sending necessarily names
    that field, and that history is worth keeping. A docstring cannot be sent to a
    provider, cannot be a default, and cannot be compared against -- so it is
    excluded, and every other string constant is not.
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, _SCOPES):
            docstring = _docstring_node(node)
            if docstring is not None:
                found.add(id(docstring))
    return found


# Which attribute holds the name, per node kind. A table rather than a branch chain:
# adding a kind is a row, and the lookup itself cannot grow more complex.
_NAME_ATTRIBUTE: tuple[tuple[type[ast.AST], str], ...] = (
    (ast.Name, "id"),
    (ast.Attribute, "attr"),
    (ast.arg, "arg"),
    (ast.keyword, "arg"),
    (ast.FunctionDef, "name"),
    (ast.AsyncFunctionDef, "name"),
    (ast.ClassDef, "name"),
)


def _identifier(node: ast.AST) -> str | None:
    """The name a node introduces or reads, if it is one of the carrying kinds."""
    for kind, attribute in _NAME_ATTRIBUTE:
        if isinstance(node, kind):
            value = getattr(node, attribute, None)
            return value if isinstance(value, str) else None
    return None


def _executable_string(node: ast.AST, prose: set[int]) -> str | None:
    """A string constant the code can act on, as opposed to a docstring."""
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return None
    if id(node) in prose:
        return None
    return node.value


def literals_and_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Every executable string constant, and every identifier that could carry AWS identity.

    Docstrings and comments are prose about the retired model; a string the code can
    actually send, default to, or compare against is the thing this guard is about.
    Comments never reach the AST, so only docstrings need excluding explicitly.
    """
    prose = docstrings(tree)
    nodes = tuple(ast.walk(tree))
    literals = {
        value for node in nodes if (value := _executable_string(node, prose)) is not None
    }
    names = {name for node in nodes if (name := _identifier(node)) is not None}
    return literals, names


# --- the haystack, before anything is concluded from its emptiness -----------


# Files that must be in any correct scan. A path typo or a package rename makes the
# absence claims below vacuous, and this is what notices.
EXPECTED_IN_SCAN = ("storage.py", "envelope.py", "config.py", "wiring.py", "intake.py")

MINIMUM_SCANNED_FILES = 40


def test_the_scan_walks_the_active_packages() -> None:
    """Without this, every absence claim below passes vacuously on a path typo."""
    assert len(scanned_files()) > MINIMUM_SCANNED_FILES


@pytest.mark.parametrize("expected", EXPECTED_IN_SCAN)
def test_each_storage_module_is_scanned(expected: str) -> None:
    assert expected in {path.name for path in scanned_files()}


def test_the_migrations_are_scanned() -> None:
    assert any(path.parent.name == "versions" for path in scanned_files())


def test_the_frozen_infra_package_is_not_scanned() -> None:
    assert not any(EXCLUDED in path.parents for path in scanned_files())


def test_the_frozen_infra_package_still_exists_and_is_excluded() -> None:
    """The exclusion must name a real directory, or it excludes nothing."""
    assert EXCLUDED.is_dir()
    assert any(EXCLUDED.glob("*.py"))


# --- the absence claims -----------------------------------------------------


@pytest.mark.parametrize("path", scanned_files(), ids=lambda p: p.name)
def test_no_aws_specific_value_appears_in_the_active_path(path: Path) -> None:
    literals, names = literals_and_names(ast.parse(path.read_text(encoding="utf-8")))

    for forbidden in FORBIDDEN_LITERALS:
        assert forbidden not in literals, f"{path.name} carries the literal {forbidden!r}"
    for forbidden in FORBIDDEN_NAMES:
        assert forbidden not in names, f"{path.name} declares or reads {forbidden!r}"


def _providers_named(values: set[str]) -> set[str]:
    """Every provider name appearing anywhere in the given strings."""
    lowered = {value.lower() for value in values}
    return {p for p in PROVIDER_NAMES if any(p in value for value in lowered)}


@pytest.mark.parametrize("path", scanned_files(), ids=lambda p: p.name)
def test_no_provider_is_named_in_the_active_path(path: Path) -> None:
    """A provider branch is the shape `KHEPRI-DEC-008` §3 forbids outright."""
    literals, names = literals_and_names(ast.parse(path.read_text(encoding="utf-8")))

    assert _providers_named(literals | names) == set()


def test_the_provider_guard_would_notice_a_branch() -> None:
    """It must be able to fail, and must not fire on this repository's own names."""
    offending, _ = literals_and_names(ast.parse('if p == "digitalocean":\n    pass\n'))
    assert "digitalocean" in offending

    _, benign = literals_and_names(ast.parse("class LocalStack:\n    pass\n"))
    assert not any(
        provider in name.lower() for name in benign for provider in PROVIDER_NAMES
    )


def test_the_guard_would_notice_a_reintroduced_value() -> None:
    """The scan must be able to fail, or it proves nothing about the files above."""
    literals, names = literals_and_names(
        ast.parse('X = "aws:kms"\ndef f(kms_key_arn: str) -> None: ...\n')
    )

    assert "aws:kms" in literals
    assert "kms_key_arn" in names
