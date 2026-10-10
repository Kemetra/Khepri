"""RRA-017 Verification 7, and the code half of Verification 12, read from the code (`#595`).

**Verification 7.** Every module under the *installed* `khepri` package is swept (anchored on
`khepri.__file__`, never the working directory) for code that builds an engine. Only
`khepri.runtime.db_roles` may build one, and every composition root names the `FR-270` role it
connects as. The sweep composition is then built for real and its object graph walked: the
components whose own attributes hold the sweep role's session factory, compared at
constructor-argument level, must be exactly `FR-271`'s four. An RCA sweeper or a
`DeletionService` that receives it fails. `khepri-envelope-migrate`'s composition is walked the
same way, and its one recipient is `FR-273`'s session lister.

**Verification 12, the code half.** Every transaction a `khepri.rra` module opens goes through
the scope helper, so none reaches a covered table without `SET LOCAL`. The exceptions are named
in `UNSCOPED`, each with its reason: `FR-231`'s pre-scope `rra_invitations`, the sweep engine's
admitted purge, and the envelope migration's session listing (`FR-273`). The four
definer calls live in one module, `khepri/rra/definer_calls.py`, beside the scope helper.

RED at `0c1475f`: engines are built in three modules, no root names a role, the sweep composition
takes one factory, and every store opens its own transactions.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

import khepri
from tests.rra017_support import Rra017Absent, future, require

PACKAGE = Path(khepri.__file__).resolve().parent
REPO = PACKAGE.parents[1]
ENGINE_BUILDERS = frozenset({"create_engine", "engine_from_config"})
ROLE_MODULE = "runtime/db_roles.py"

#: `FR-270`: each composition root and the roles it connects as.
ROOT_ROLES = {
    "runtime/web.py": {"APPLICATION"},
    "runtime/worker.py": {"WORKER"},
    "runtime/retention_sweep.py": {"APPLICATION", "SWEEP"},
    "runtime/envelope_migration.py": {"APPLICATION", "SWEEP"},
    "runtime/clerk_hard_stop.py": {"APPLICATION"},
    "local/app.py": {"APPLICATION"},
    "local/cli.py": {"APPLICATION", "WORKER", "SWEEP"},
}
#: `FR-271`'s four sweep-engine recipients, by class name.
SWEEP_RECIPIENTS = frozenset(
    {"ExpiredSessionLister", "DueUploadLister", "SqlDeletionRepository", "RecoveryCandidates"}
)
#: `FR-273`'s one sweep-engine recipient in `khepri-envelope-migrate`'s composition.
ENVELOPE_RECIPIENTS = frozenset({"EnvelopeSessionLister"})
#: Transactions a `khepri.rra` module may open without a scope, each with its reason.
UNSCOPED = {
    ("persistence.py", "add_invitation"): "FR-231: rra_invitations is pre-scope",
    ("persistence.py", "get_invitation"): "FR-231: rra_invitations is pre-scope",
    ("persistence.py", "purge_evidence_before"): "FR-271: the sweep engine's admitted purge",
    ("persistence.py", "redeem_invitation"): "FR-233: mints the owner, apply_scope before insert",
    ("claim_queue.py", "_next_claimable"): "FR-267: the definer picker is the scope's source",
    ("envelope_migration.py", "sessions"): "FR-273: the sweep engine's session listing",
}
#: The scope helper, and the one module that calls `FR-264`'s four definer functions.
SCOPE_MODULES = frozenset({"scope.py", "definer_calls.py"})


def _modules(root: Path) -> Iterator[tuple[str, ast.Module]]:
    for path in sorted(root.rglob("*.py")):
        yield path.relative_to(PACKAGE).as_posix(), ast.parse(path.read_text(encoding="utf-8"))


def _called(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    function = node.func
    return function.id if isinstance(function, ast.Name) else getattr(function, "attr", None)


def test_only_the_role_module_builds_an_engine() -> None:
    builders = {
        name
        for name, tree in _modules(PACKAGE)
        if any(_called(node) in ENGINE_BUILDERS for node in ast.walk(tree))
    }
    require(builders == {ROLE_MODULE}, f"engines are built in {sorted(builders)}")


def _roles_named(tree: ast.Module) -> set[str]:
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "DatabaseRole"
    }


def test_every_composition_root_names_exactly_its_fr270_roles() -> None:
    named = {
        name: roles
        for name, tree in _modules(PACKAGE)
        if (roles := _roles_named(tree)) and name != ROLE_MODULE and name != "runtime/config.py"
    }
    require(named == ROOT_ROLES, f"roots name {named}")


def test_only_the_migrations_read_the_migration_owners_credential() -> None:
    variable = "KHEPRI_MIGRATION_DATABASE_SECRET"
    readers = {name for name, tree in _modules(PACKAGE) if variable in ast.unparse(tree)}
    env = (REPO / "migrations" / "env.py").read_text(encoding="utf-8")
    require("MIGRATION_DATABASE_SECRET" in env, "migrations/env.py does not read it")
    require(
        readers == {"runtime/config.py"}, f"also read by {sorted(readers - {'runtime/config.py'})}"
    )


# -- the sweep composition, by construction --------------------------------------------------


def _holders(root: Any, target: Any) -> set[str]:
    """Classes of every object reachable from `root` whose own attribute is `target`."""
    found: set[str] = set()
    seen: set[int] = set()
    stack = [root]
    while stack:
        current = stack.pop()
        if id(current) in seen or isinstance(
            current, str | bytes | int | float | bool | type(None)
        ):
            continue
        seen.add(id(current))
        children = _children(current)
        if any(child is target for child in children):
            found.add(type(current).__name__)
        stack.extend(child for child in children if child is not target)
    return found


def _children(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, list | tuple | set | frozenset):
        return list(value)
    if isinstance(value, sessionmaker):
        return []
    attributes = getattr(value, "__dict__", {})
    slots = [
        getattr(value, slot, None)
        for cls in type(value).__mro__
        for slot in getattr(cls, "__slots__", ())
    ]
    return [*attributes.values(), *slots]


def _runtime_sweep(sweep: sessionmaker[Session]) -> Any:
    from tests.test_runtime_wiring import runtime_stack  # noqa: PLC0415

    build = future("khepri.runtime.wiring", "build_retention_sweep")
    if "sweep_factory" not in inspect.signature(build).parameters:
        raise Rra017Absent("build_retention_sweep takes no sweep engine yet (FR-271)")
    return build(runtime_stack(), sweep_factory=sweep)


def _local_sweep(sweep: sessionmaker[Session]) -> Any:
    """Over a stand-in stack: the local `build_stack` reaches the object store at construction.

    The sweep composition reads the stack's scoped factory and object store, and nothing else.
    """
    build = future("khepri.local.wiring", "build_sweeper")
    return build(SimpleNamespace(factory=sessionmaker(), objects=object()), sweep_factory=sweep)


@pytest.mark.parametrize("compose", [_runtime_sweep, _local_sweep], ids=["runtime", "local"])
def test_the_sweep_engine_reaches_exactly_fr271s_four_components(compose: Any) -> None:
    sweep = sessionmaker()
    holders = _holders(compose(sweep), sweep)
    require(holders == SWEEP_RECIPIENTS, f"the sweep factory reaches {sorted(holders)}")


@pytest.mark.parametrize("compose", [_runtime_sweep, _local_sweep], ids=["runtime", "local"])
def test_no_deletion_service_is_built_over_the_sweep_engine(compose: Any) -> None:
    from khepri.rra.deletion import DeletionService  # noqa: PLC0415

    sweep = sessionmaker()
    root = compose(sweep)
    services = [obj for obj in _reachable(root) if isinstance(obj, DeletionService)]
    require(bool(services), "the sweep holds no DeletionService of its own")
    for service in services:
        require(not _holders(service, sweep), "a DeletionService reaches the sweep engine")


def _envelope_migration(sweep: sessionmaker[Session]) -> Any:
    build = future("khepri.runtime.envelope_migration", "build_envelope_migration")
    if "sweep_factory" not in inspect.signature(build).parameters:
        raise Rra017Absent("build_envelope_migration takes no sweep engine yet (FR-273)")
    stack = SimpleNamespace(factory=sessionmaker(), objects=object(), clock=object())
    return build(stack, sweep_factory=sweep)


def test_the_sweep_engine_reaches_exactly_fr273s_session_lister() -> None:
    """`FR-273`: in the envelope migration the sweep engine goes to the lister and nothing else.
    A lister handed the scoped engine instead holds no sweep engine, and fails here too."""
    sweep = sessionmaker()
    holders = _holders(_envelope_migration(sweep), sweep)
    require(holders == ENVELOPE_RECIPIENTS, f"the sweep factory reaches {sorted(holders)}")


def test_every_sweep_engine_recipient_is_fr271s_four_or_fr273s_lister() -> None:
    """Verification 7: across every composition, the set equals `FR-271`'s list with the lister."""
    found: set[str] = set()
    for compose in (_runtime_sweep, _local_sweep, _envelope_migration):
        sweep = sessionmaker()
        found |= _holders(compose(sweep), sweep)
    require(found == SWEEP_RECIPIENTS | ENVELOPE_RECIPIENTS, f"recipients are {sorted(found)}")


def test_the_envelope_listers_scoped_twin_is_not_the_stacks_engine() -> None:
    """The stack's scoped engine reaches the migration's per-session work, never the lister."""
    stack_factory = sessionmaker()
    build = future("khepri.runtime.envelope_migration", "build_envelope_migration")
    stack = SimpleNamespace(factory=stack_factory, objects=object(), clock=object())
    migration = build(stack, sweep_factory=sessionmaker())
    require(
        "EnvelopeSessionLister" not in _holders(migration, stack_factory),
        "the session lister holds the scoped engine",
    )


def test_no_local_wiring_hands_a_scoped_factory_to_the_sweep() -> None:
    """`FR-271`: `sweep_factory=stack.factory` binds the four cross-scope reads to a scoped role.

    The scope tripwire then refuses each unscoped statement and the sweep reports the passes as
    faulted. Only a root holding the sweep role's credential may build its factory (`FR-270`).
    """
    scoped = [
        f"{name}:{keyword.value.lineno}"
        for name, tree in _modules(PACKAGE / "local")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "sweep_factory"
        and isinstance(keyword.value, ast.Attribute)
        and keyword.value.attr == "factory"
    ]
    assert not scoped, f"a scoped factory reaches the sweep at {scoped}"


def _reachable(root: Any) -> Iterator[Any]:
    seen: set[int] = set()
    stack = [root]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        stack.extend(_children(current))


# -- Verification 12, the code half -----------------------------------------------------------


def _opens_a_transaction(node: ast.AST) -> bool:
    """`factory()`, `factory.begin()`, `self._factory()`, `self._factory.begin()`."""
    if not isinstance(node, ast.Call):
        return False
    function = node.func
    if isinstance(function, ast.Attribute) and function.attr == "begin":
        function = function.value
    name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", "")
    return name.endswith("factory")


def _functions(tree: ast.Module) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    return (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef))


def _opened_in(function: ast.AST) -> list[int]:
    return [
        item.context_expr.lineno
        for item in ast.walk(function)
        if isinstance(item, ast.withitem) and _opens_a_transaction(item.context_expr)
    ]


def _unscoped_in(short: str, tree: ast.Module) -> list[str]:
    return [
        f"{short}:{function.name}:{line}"
        for function in _functions(tree)
        if (short, function.name) not in UNSCOPED
        for line in _opened_in(function)
    ]


def _unscoped_transactions() -> list[str]:
    """`module:function:line` for every transaction opened outside the scope helper."""
    modules = ((name.removeprefix("rra/"), tree) for name, tree in _modules(PACKAGE / "rra"))
    return [
        offender
        for short, tree in modules
        if short not in SCOPE_MODULES
        for offender in _unscoped_in(short, tree)
    ]


def test_every_rra_transaction_opens_through_the_scope_helper() -> None:
    offenders = _unscoped_transactions()
    require(offenders == [], f"{len(offenders)} transactions open without a scope: {offenders}")
