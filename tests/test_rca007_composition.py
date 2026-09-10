"""`RCA-007` — the composition, and the checks that stand between it and a wrong figure.

Authority: active `RCA-007` `FR-151`--`FR-158`.

`SV1-08` proved the two halves refused each other. These prove they now meet,
and that every way the bridge can fail ends at `RCA-006` `FR-146`'s one
content-free unavailable outcome rather than at a projection nobody vouched for.

**The two checks are the point, not the plumbing.** `ReportBundle.of` runs
`RRA-004`'s derivation, and `KHEPRI-DEC-032` admitted that constructor for
callers that publish no figure. A semantic view publishes figures, so `RCA-007`
put the question to the owner and its merge was the ruling: determinism is
protected by checks rather than avoidance. `test_a_moved_version_triple_...` and
`test_a_document_that_drifted_...` are those checks, and each is driven by a
mutated stored row rather than by a stub, because a check nothing can trip is
not a check.

**Every miss is compared against another miss, never against a fixture.** Four
conditions have to be indistinguishable; four outcomes each equal to
`ViewOutcome(kind="unavailable")` would still pass if three drifted together
away from the fourth in a field a later slice adds.
"""

from __future__ import annotations

import ast
import hashlib
import pathlib
from dataclasses import dataclass

from sqlalchemy import event, select, update

from khepri.rca.isolation import IsolationService
from khepri.rca.persistence import SqlAccountStore
from khepri.rca.semantic_queries import ports, queries
from khepri.rra.packages import FactPackageRecord
from khepri.rra.persistence import FactPackageRow, SqlFactPackageRepository
from khepri.rra.profiling import canonical_json
from khepri.runtime import semantic_view_adapter
from khepri.runtime.semantic_view_adapter import SemanticViewAdapter
from tests.c106_support import completed_pair
from tests.w104_support import Member, member
from tests.w104b_support import Journey, journey

MISSING_ID = "no-such-source"

#: Statements that change rows. `FR-155` admits none of them on this path.
_WRITE_VERBS = ("insert", "update", "delete", "merge", "replace", "upsert")


def _actions(j: Journey, who: Member) -> queries.SemanticQueryActions:
    """The real orchestration over the real stores and the real adapter."""
    return queries.SemanticQueryActions(
        isolation=IsolationService(j.w.organizations, SqlAccountStore(j.w.factory)),
        sources=j.w.store,
        port=SemanticViewAdapter(SqlFactPackageRepository(j.w.factory)),
    )


def _request(who: Member, *source_ids: str) -> queries.SemanticQueryRequest:
    """`who` asking for the overview over the named sources in their organization."""
    return queries.SemanticQueryRequest(
        actor=queries.SemanticQueryActor(account_id=who.account_id),
        organization_id=who.organization_id,
        view=ports.SemanticViewRequest(
            view_id="ExecutiveOverviewView",
            view_version="sv1.executive_overview.v1",
        ),
        source_ids=source_ids,
    )


def test_a_scoped_run_now_reaches_a_real_projection() -> None:
    """The composition `SV1-08` recorded NOT EXERCISED, exercised.

    Before `RCA-007` this exact request answered
    `ViewRefusal('incompatible source shape')` every time.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)

    outcome = _actions(j, who).request(_request(who, pair.subject_run.run_id))

    assert outcome.kind == ports.KIND_ADMITTED
    assert outcome.projection is not None
    assert outcome.projection.rows


def test_the_projection_carries_the_packages_own_values_and_versions() -> None:
    """`FR-152` -- the adapter added nothing. Compared against the package, not a copy.

    Asserted against the record the run names rather than against a second
    projection: two projections agree when both dropped the same field.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    run = pair.subject_run

    outcome = _actions(j, who).request(_request(who, run.run_id))

    assert outcome.projection is not None
    stated = dict(outcome.projection.version_pairs)
    assert stated["package"] == run.package_version
    assert stated["formula"] == run.formula_version


def test_every_way_the_bridge_can_miss_answers_the_same_way() -> None:
    """`FR-151` -- absent, cross-scope and package-less are one outcome.

    The third is made package-less by deleting the package row the run names,
    which leaves a completed run pointing at nothing -- the state a retention
    sweep produces and the one a stub would never reproduce faithfully.

    **Order matters, and a first version got it wrong.** The delete ran before
    the cross-scope request, so that request would have answered `unavailable`
    for the wrong reason -- a missing package rather than a foreign scope -- and
    the equality would have held even with scope enforcement gone. The foreign
    run is asked for while its package is still there.
    """
    j = journey()
    who = member(j.w)
    other = member(j.w, email="other@example.test", name="Other")
    pair = completed_pair(j, who)
    run = pair.subject_run

    absent = _actions(j, who).request(_request(who, MISSING_ID))
    cross_scope = _actions(j, other).request(_request(other, run.run_id))
    _delete_package(j, run.package_digest)
    package_less = _actions(j, who).request(_request(who, run.run_id))

    assert absent.kind == ports.KIND_UNAVAILABLE
    assert cross_scope == absent
    assert package_less == absent


def _delete_package(j: Journey, digest: str) -> None:
    """Remove the package row a run names, leaving the run itself intact."""
    with j.w.factory() as database:
        row = database.scalars(
            select(FactPackageRow).where(FactPackageRow.package_digest == digest)
        ).first()
        assert row is not None, "the fixture never wrote the package this test deletes"
        database.delete(row)
        database.commit()


def test_a_document_that_drifted_from_its_digest_is_unavailable() -> None:
    """`FR-153` -- a package that cannot vouch for itself projects nothing.

    The stored document is mutated in place so the rebuild no longer matches the
    digest the record names. Driven through the row rather than a stub, because
    the check exists for a stored document and a stub would prove only that the
    branch exists.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    run = pair.subject_run
    _corrupt_document(j, run.package_digest)

    outcome = _actions(j, who).request(_request(who, run.run_id))

    assert outcome.kind == ports.KIND_UNAVAILABLE


def _corrupt_document(j: Journey, digest: str) -> None:
    """Change one governed value inside the stored document, leaving the digest."""
    with j.w.factory() as database:
        row = database.scalars(
            select(FactPackageRow).where(FactPackageRow.package_digest == digest)
        ).first()
        assert row is not None, "the fixture never wrote the package this test corrupts"
        document = dict(row.document)
        document["row_count"] = int(document.get("row_count", 0)) + 1
        database.execute(
            update(FactPackageRow)
            .where(FactPackageRow.package_id == row.package_id)
            .values(document=document)
        )
        database.commit()


def test_a_moved_version_triple_stops_the_path() -> None:
    """`FR-157` -- the check `RCA-007`'s merged position undertook to make.

    A package whose recorded versions no longer match the run's would let a view
    publish figures under semantics no delivered surface ran. That is the failure
    the determinism reading of `RRA-011`:204 names, and it is refused here rather
    than argued away.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    run = pair.subject_run
    _move_formula_version(j, run.package_digest)

    outcome = _actions(j, who).request(_request(who, run.run_id))

    assert outcome.kind == ports.KIND_UNAVAILABLE


def _move_formula_version(j: Journey, digest: str) -> None:
    """Advance the stored package's formula version past the run's recorded one."""
    with j.w.factory() as database:
        database.execute(
            update(FactPackageRow)
            .where(FactPackageRow.package_digest == digest)
            .values(formula_version="rra004.formula.v999")
        )
        database.commit()


def test_repeating_one_request_returns_the_same_projection() -> None:
    """The rebuild is stable, so a view repeats a value rather than answering afresh."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = _actions(j, who)

    outcomes = [actions.request(_request(who, pair.subject_run.run_id)) for _ in range(3)]

    assert outcomes[0].kind == ports.KIND_ADMITTED
    assert all(outcome == outcomes[0] for outcome in outcomes)


def test_the_composed_request_writes_nothing() -> None:
    """`FR-155` -- zero writes, asserted at the connection over every store.

    Both paths are driven: the one that projects and the one that misses. A
    listener that saw no statement at all would prove nothing, so it is asserted
    to have seen some.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = _actions(j, who)
    statements: list[str] = []

    def _record(_conn, _cursor, statement, _params, _context, _many) -> None:  # noqa: ANN001
        statements.append(statement)

    engine = j.w.factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", _record)
    try:
        actions.request(_request(who, pair.subject_run.run_id))
        actions.request(_request(who, MISSING_ID))
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert statements, "the listener saw nothing, so it proves nothing"
    written = [s for s in statements if s.strip().split(" ")[0].lower() in _WRITE_VERBS]
    assert written == [], f"the composed path issued a write: {written}"


def _adapter_source() -> str:
    """The adapter module's own text, for the static assertions below."""
    return pathlib.Path(semantic_view_adapter.__file__).read_text(encoding="utf-8")


def _imported_roots(source: str) -> set[str]:
    """Every top-level module name `source` imports, in either import form.

    Both node types, because a scan that reads only `ast.ImportFrom` is blind to
    a plain `import fastapi` -- which is exactly the import these boundary
    assertions exist to catch. A first version of this file had that hole in
    three places.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or "").split(".")[0])
    return roots


def _imported_modules(source: str) -> set[str]:
    """Every fully-qualified module name `source` imports, in either form."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    return names


def test_the_adapter_serves_no_route_and_no_response() -> None:
    """`FR-158` -- `report_api.py`'s boundary is untouched by this module.

    A figure-returning route would be an `RRA-006` surface. This module returns a
    projection to `RCA-006` in process and imports nothing that could answer HTTP.
    """
    imported = _imported_roots(_adapter_source())

    assert "fastapi" not in imported
    assert "starlette" not in imported
    assert "@app." not in _adapter_source()


def test_the_rca_package_still_imports_no_concrete_rra() -> None:
    """`FR-154` -- the binding lives in the composition root and only there.

    `RCA-006`'s no-concrete-import property is what the adapter exists to
    preserve: `khepri.rca` still speaks only to a protocol, and `khepri.runtime`
    is the one place that names both packages.
    """
    package = pathlib.Path(queries.__file__).parent
    sources = tuple(sorted(package.glob("*.py")))
    assert len(sources) >= 3, f"the scan found too few files to be scanning anything: {sources}"

    offenders = [
        f"{path.name}: {name}"
        for path in sources
        for name in sorted(_imported_modules(path.read_text(encoding="utf-8")))
        if name.startswith("khepri.rra")
    ]
    assert offenders == [], f"the RCA package reached a concrete RRA module: {offenders}"


def test_the_adapter_is_the_only_runtime_module_reaching_the_projection() -> None:
    """`FR-154` -- one composition root, found rather than assumed.

    A first version of this test looked for a module importing *both* halves and
    found none, including the adapter: it never imports `khepri.rca` at all,
    because it satisfies the port structurally and is handed to
    `SemanticQueryActions` by whoever composes them. That is the property
    `RCA-006` wanted and the test was wrong, not the code. What a second
    composition root would actually look like is a second `khepri.runtime`
    module reaching into the semantic-view package, so that is what is asserted.
    """
    runtime = pathlib.Path(semantic_view_adapter.__file__).parent
    sources = tuple(sorted(runtime.glob("*.py")))
    assert len(sources) >= 5, f"the scan found too few files to be scanning anything: {sources}"

    binders = [path.name for path in sources if _reaches_semantic_views(path)]

    assert binders == ["semantic_view_adapter.py"], f"more than one binding: {binders}"


def _reaches_semantic_views(path: pathlib.Path) -> bool:
    """Whether a runtime module imports the `RRA-014` semantic-view package."""
    return any(
        name.startswith("khepri.rra.semantic_views")
        for name in _imported_modules(path.read_text(encoding="utf-8"))
    )


# --- The adapter on its own -------------------------------------------------
#
# Everything above drives the adapter through `SemanticQueryActions`, and a
# mutation round showed that hides three of its guards: the orchestration
# refuses a cross-scope run at `get_analysis_run` before the adapter sees it, and
# `FactPackageRecord.verify` raises on a tampered row before the adapter's own
# checks run. Dropping the owner scope from the package read, deleting the
# version-triple check and accepting a non-run source all survived. So the
# adapter is also driven directly here, which is where those three live.


@dataclass(frozen=True, slots=True)
class _RunLike:
    """The four members the adapter reads off a source, and nothing else."""

    owner_id: str
    package_digest: str | None
    package_version: str | None
    formula_version: str | None


def _run_like(run: object, **overrides: object) -> _RunLike:
    """A stand-in for one real run, with named fields varied."""
    fields: dict[str, object] = {
        "owner_id": run.owner_id,  # type: ignore[attr-defined]
        "package_digest": run.package_digest,  # type: ignore[attr-defined]
        "package_version": run.package_version,  # type: ignore[attr-defined]
        "formula_version": run.formula_version,  # type: ignore[attr-defined]
    }
    return _RunLike(**(fields | overrides))  # type: ignore[arg-type]


def _view() -> ports.SemanticViewRequest:
    """The overview request the adapter-level cases project."""
    return ports.SemanticViewRequest(
        view_id="ExecutiveOverviewView", view_version="sv1.executive_overview.v1"
    )


def test_the_adapter_reads_the_package_under_the_runs_own_scope() -> None:
    """`FR-151` at the adapter, not at the orchestration in front of it.

    The composed cross-scope case never reaches here: `SemanticQueryActions`
    refuses the run first. Dropping `owner_id` from the package read therefore
    survived that test. This hands the adapter a run naming a real package under
    somebody else's scope, which is the only way to see the read's own filter.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    adapter = SemanticViewAdapter(SqlFactPackageRepository(j.w.factory))
    trespasser = _run_like(pair.subject_run, owner_id="own_someone_else")

    assert adapter.project(_view(), (trespasser,)) is None
    assert adapter.project(_view(), (_run_like(pair.subject_run),)) is not None


def test_the_adapter_refuses_a_run_whose_versions_left_its_package_behind() -> None:
    """`FR-157` at the adapter. The composed case proved the wrong thing.

    Mutating the *package row*'s version made it contradict its own document, so
    `FactPackageRecord.verify` raised before the adapter's check ran and deleting
    that check survived. The real `FR-157` condition is a package that is
    internally consistent but no longer matches the *run*, so the run is what
    moves here.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    adapter = SemanticViewAdapter(SqlFactPackageRepository(j.w.factory))

    moved = _run_like(pair.subject_run, formula_version="rra004.formula.v999")

    assert adapter.project(_view(), (moved,)) is None


def test_the_adapter_refuses_a_source_that_is_not_a_completed_run() -> None:
    """A run that never derived a package, and an object that is not a run.

    Neither reaches the adapter through the orchestration -- a run with no
    package still loads, but the composed suite never builds one -- so accepting
    any source survived the composed cases.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    adapter = SemanticViewAdapter(SqlFactPackageRepository(j.w.factory))

    assert adapter.project(_view(), (object(),)) is None
    assert adapter.project(_view(), (_run_like(pair.subject_run, package_digest=None),)) is None
    assert _refuses_before_reading(j, pair.subject_run)


def _refuses_before_reading(j: Journey, run: object) -> bool:
    """Whether a run with no package digest is refused *without* asking the reader.

    Through the database this cannot be seen: `get_owned_package(None, ...)`
    matches no row, so deleting the digest guard survived. The property is real
    all the same -- a run that never derived a package must not send the reader
    looking -- and a reader that answers anything shows it. With the guard the
    answer is `None`; without it the stub's record comes back and projects.
    """
    with j.w.factory() as database:
        row = database.scalars(
            select(FactPackageRow).where(
                FactPackageRow.package_digest == run.package_digest  # type: ignore[attr-defined]
            )
        ).first()
        assert row is not None
        record = _record_claiming_digest(row, row.package_digest)
    adapter = SemanticViewAdapter(_UnverifiedPackages(record))  # type: ignore[arg-type]
    return adapter.project(_view(), (_run_like(run, package_digest=None),)) is None


class _UnverifiedPackages:
    """A reader that answers with a record no `verify()` ever saw.

    The only way to reach the adapter's rebuilt-digest check. A stored row cannot
    get past `FactPackageRecord.verify` with a digest that disagrees with its
    document, so through the database that branch is unreachable -- it exists to
    catch a *rebuild* that starts losing or inventing a field, which is what
    `package_source.py` says its own copy of this check is for. Driving it needs
    a record built by hand, and that is what this is.
    """

    def __init__(self, record: object) -> None:
        """Answer every read with `record`, unverified."""
        self._record = record

    def get_owned_package(self, package_digest: str, owner_id: str) -> object:
        """The record as given, whatever it says about itself."""
        return self._record


def test_the_adapter_refuses_a_package_whose_rebuild_does_not_match_its_digest() -> None:
    """`FR-153`'s second check: the rebuilt package, not the stored document.

    `verify()` hashes the document; this compares the digest of what the rebuild
    produced. Removing it survived every database-driven case, because no stored
    row can reach it. That does not make it decoration -- it makes it the guard
    against a lossy rebuild, and this is the input that shows it holding.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    with j.w.factory() as database:
        row = database.scalars(
            select(FactPackageRow).where(
                FactPackageRow.package_digest == pair.subject_run.package_digest
            )
        ).first()
        assert row is not None
        record = _record_claiming_digest(row, "0" * 64)
    adapter = SemanticViewAdapter(_UnverifiedPackages(record))  # type: ignore[arg-type]

    assert adapter.project(_view(), (_run_like(pair.subject_run),)) is None


def _record_claiming_digest(row: FactPackageRow, digest: str) -> FactPackageRecord:
    """The row's own package record, claiming a digest its document will not hash to."""
    return FactPackageRecord(
        package_id=row.package_id,
        owner_id=row.owner_id,
        session_id=row.session_id,
        profile_id=row.profile_id,
        package_version=row.package_version,
        formula_version=row.formula_version,
        mapping_version=row.mapping_version,
        profile_document_digest=row.profile_document_digest,
        source_sha256_hex=row.source_sha256_hex,
        package_digest=digest,
        row_count=row.row_count,
        created_at=row.created_at,
        document=dict(row.document),
    )


def test_the_mapping_version_is_bound_by_the_digest_not_by_a_comparison() -> None:
    """`FR-157`'s third leg, which `_versions_agree` does not compare and need not.

    `AnalysisRun` records `package_digest`, `package_version` and
    `formula_version`, and no mapping version -- so there is nothing on the run
    to compare a mapping version against. That is not a hole: the run names its
    package *by digest*, `FactPackageRecord.verify` refuses a record whose
    `mapping_version` disagrees with its document, and the digest is the hash of
    that document. A package with a different mapping version therefore has a
    different digest and no run can reach it.

    Asserted here rather than argued, because "the digest covers it" is the kind
    of claim that is true until someone changes what the digest covers.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    with j.w.factory() as database:
        row = database.scalars(
            select(FactPackageRow).where(
                FactPackageRow.package_digest == pair.subject_run.package_digest
            )
        ).first()
        assert row is not None
        document = dict(row.document)

    assert document["mapping_version"] == row.mapping_version
    assert _digest_of(document) == row.package_digest
    assert _digest_of({**document, "mapping_version": "rra004.mapping.v999"}) != row.package_digest


def _digest_of(document: dict[str, object]) -> str:
    """The digest a stored package document hashes to, computed independently."""
    return hashlib.sha256(canonical_json(document).encode()).hexdigest()
