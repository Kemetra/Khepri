"""`SV1-08` — the latency and query-shape baseline, and the half that has none.

Authority: active `RRA-014` `FR-144`, "latency and query-shape evidence may
measure execution but may not add caching, pre-aggregation, materialized views,
sampling, or result changes".

**The end-to-end latency baseline is NOT EXERCISED, and this module proves the
reason rather than asserting it.** `SV1-04` resolved the runtime adapter's scope
question against building one: `RCA-006` §Scope governs no runtime wiring, so
nothing in the image binds the RRA half to the RCA half. The allocation plan
anticipated that a figure taken over a test-local fake port would measure the
fake. The truth is sharper, and
`test_the_shipped_halves_do_not_compose_so_there_is_no_end_to_end_path` shows
it: composed by hand, with the real isolation door, the real workspace store,
the real orchestration and the real projection and no fake anywhere, a request
for a published view over a real `AnalysisRun` returns
`ViewRefusal('incompatible source shape')` every time. `SemanticQueryActions`
loads `AnalysisRun` rows; `project` admits a `RenderableBundle`; the two do not
meet. The deferred adapter is therefore not a wiring line but a bundle
construction, and *that unbuilt step is where the end-to-end latency and the
real source-acquisition query shape both live*. Measuring around it would
publish a baseline for a path that does not exist.

**What is measurable is measured, over shipped code and with no fake.** The
query shape of the orchestration -- one scope resolution, then exactly one
scoped read per named source in the caller's order, then one projection -- is
`SemanticQueryActions`' own behaviour, recorded by a reader that counts calls
without influencing them. It does not vary by view, because no view issues a
query: the RRA half is handed its source and reads nothing, which
`test_the_projection_half_issues_no_read_at_all` scans for. And the projection
half's own latency is a real distribution over the real `project` and a real
bundle. The measured numbers live in the dated evidence ledger beside this
slice; what is asserted here is that the distribution was collected and that
every sample in it returned an equal result, because a wall-clock threshold in
CI is a flake, not a baseline.

**`FR-144` bars the measurement from changing what it measures.** This slice
adds no source file: `src/khepri/rra/semantic_views/` and
`src/khepri/rca/semantic_queries/` are byte-identical before and after it, which
is the "zero additions to any read path" the plan asks for, and
`test_the_read_path_gained_no_measurement_module` holds the module set closed so
a later timing helper cannot be slipped in. The four remaining prohibitions --
caching, pre-aggregation, materialized views, sampling -- are transcribed into
`PROHIBITIONS` and scanned for, one test each, so a prohibition added to the
requirement and forgotten here fails `test_every_prohibition_has_a_test` rather
than passing silently. `SV1-07`'s discipline: a scan cannot find a rule nobody
wrote down.
"""

from __future__ import annotations

import ast
import pathlib
import statistics
import time

import pytest

from khepri.rca.isolation import IsolationService
from khepri.rca.persistence import SqlAccountStore
from khepri.rca.semantic_queries import ports, queries
from khepri.rra.persistence import SqlFactPackageRepository
from khepri.rra.semantic_views import contracts, projection, refusals, registry
from khepri.runtime.semantic_view_adapter import SemanticViewAdapter
from tests.c105_support import _bundle as _c105_bundle
from tests.c105_support import build_comparison_request
from tests.c106_support import completed_pair
from tests.test_sv104_query_orchestration import _FakePort, _SpyReader
from tests.test_sv105_propagation import _EXACT, _bundle, _figure
from tests.w104_support import Member, member
from tests.w104b_support import Journey, journey

#: `FR-144`'s five prohibitions, transcribed from the requirement sentence in its
#: own order. Each name has a `test_no_..._<name>` below and
#: `test_every_prohibition_has_a_test` asserts so.
PROHIBITIONS = (
    "caching",
    "pre_aggregation",
    "materialized_views",
    "sampling",
    "result_changes",
)

#: How many samples make a distribution rather than an anecdote. The plan's
#: acceptance: "report a distribution, not one sample".
_SAMPLES = 200

#: Names that would introduce a cached, memoized or otherwise remembered result
#: on the read path. `functools.cache` and `lru_cache` are the obvious two;
#: `cached_property` is the one that hides behind an attribute access.
_CACHING_NAMES = ("lru_cache", "cached_property", "functools.cache", "memoize")

#: Names that would pre-compute a fact the source does not state. `FR-138`
#: already bars the arithmetic; these are the storage shapes that would keep one.
_PRE_AGGREGATION_NAMES = ("groupby", "aggregate", "rollup", "precompute", "accumulate")

#: Names that would stand a stored projection in front of the live one.
_MATERIALIZED_NAMES = ("materialize", "materialized", "snapshot", "refresh_view")

#: Names that would answer from part of the source. `FR-142` makes an admitted
#: empty result a stated result; a sampled one would be neither.
_SAMPLING_NAMES = ("sample", "choice", "shuffle", "randint", "islice")

#: Timing surfaces. A production module that imports one is measuring itself,
#: which is the "result change" `FR-144`'s final clause bars.
_TIMING_MODULES = ("time", "timeit", "cProfile", "profile", "resource")

#: The modules the read path is closed to. Held as a set so a measurement helper
#: added later fails a test rather than joining the path it measures.
_RRA_MODULES = frozenset(
    {"__init__", "compatibility", "contracts", "projection", "published", "refusals", "registry"}
)
_RCA_MODULES = frozenset({"__init__", "ports", "queries"})


def _rra_package() -> pathlib.Path:
    """The RRA semantic-views package directory, found from the module itself."""
    return pathlib.Path(projection.__file__).parent


def _rca_package() -> pathlib.Path:
    """The RCA semantic-queries package directory, found from the module itself."""
    return pathlib.Path(queries.__file__).parent


def _read_path_sources() -> tuple[pathlib.Path, ...]:
    """Every module on the read path, found rather than listed."""
    return tuple(sorted([*_rra_package().glob("*.py"), *_rca_package().glob("*.py")]))


def _read_path_text() -> tuple[tuple[str, str], ...]:
    """Each read-path module as `(name, source)`, for the prohibition scans."""
    return tuple((path.name, path.read_text(encoding="utf-8")) for path in _read_path_sources())


def _offending_names(banned: tuple[str, ...]) -> list[str]:
    """Every read-path module whose code mentions one of `banned`.

    Scanned over the code with docstrings stripped, because every one of these
    words appears in a docstring here saying the package does not do it, and a
    scan that its own prose fails is a scan nobody keeps.
    """
    offenders: list[str] = []
    for name, source in _read_path_text():
        code = _code_only(source)
        offenders += [f"{name}: {word}" for word in banned if word in code]
    return offenders


def _code_only(source: str) -> str:
    """`source` with every docstring removed, so prose cannot trip a scan."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        _strip_docstring(node)
    return ast.unparse(tree)


def _strip_docstring(node: ast.AST) -> None:
    """Drop `node`'s leading string expression if it has one."""
    body = getattr(node, "body", None)
    if not isinstance(body, list) or not body:
        return
    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        _replace_first(node, body)


def _replace_first(node: ast.AST, body: list[ast.stmt]) -> None:
    """Replace the docstring statement with `pass`, keeping the block legal."""
    node.body = [ast.Pass(), *body[1:]]  # type: ignore[attr-defined]


def _imports_of(path: pathlib.Path) -> set[str]:
    """Every module name the file at `path` imports."""
    return _imported_modules(path.read_text(encoding="utf-8"))


def _imported_modules(source: str) -> set[str]:
    """Every module name `source` imports, plain and `from`-form alike."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        names |= _import_names(node)
    return names


def _import_names(node: ast.AST) -> set[str]:
    """The module names one import node names, or nothing for other nodes."""
    if isinstance(node, ast.Import):
        return {alias.name.split(".")[0] for alias in node.names}
    if isinstance(node, ast.ImportFrom):
        return {(node.module or "").split(".")[0]}
    return set()


def _actions(j: Journey, port: object, reader: object) -> queries.SemanticQueryActions:
    """The orchestration over the journey's real isolation door and stores."""
    return queries.SemanticQueryActions(
        isolation=IsolationService(j.w.organizations, SqlAccountStore(j.w.factory)),
        sources=reader,  # type: ignore[arg-type]
        port=port,  # type: ignore[arg-type]
    )


def _view(view_id: str = "ExecutiveOverviewView") -> ports.SemanticViewRequest:
    """One exact published version of `view_id`, named as `FR-143` requires."""
    definition = registry.define_view(view_id)
    return ports.SemanticViewRequest(
        view_id=definition.view_id, view_version=definition.view_version
    )


def _query(who: Member, *source_ids: str, view_id: str = "ExecutiveOverviewView"):
    """`who` asking for `view_id` over the named sources in their organization."""
    return queries.SemanticQueryRequest(
        actor=queries.SemanticQueryActor(account_id=who.account_id),
        organization_id=who.organization_id,
        view=_view(view_id),
        source_ids=source_ids,
    )


class _CountingIsolation:
    """The real isolation door behind a counter, so ordering is observable."""

    def __init__(self, inner: IsolationService, log: list[str]) -> None:
        """Wrap `inner`; every resolution appends to the shared `log`."""
        self._inner = inner
        self._log = log

    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        """Record the resolution, then serve it from the real door unchanged."""
        self._log.append("resolve")
        return self._inner.resolve_scope(account_id, organization_id)


class _LoggingPort:
    """A port that logs the projection, so the shape's tail is recorded too.

    It answers `None` -- `FR-146`'s uniform miss -- because what is being
    measured is that `project` was called once and when, not what it returned.
    """

    def __init__(self, log: list[str]) -> None:
        """Append every projection to the shared `log`."""
        self._log = log

    def project(self, request: object, sources: tuple[object, ...]) -> None:
        """Record the projection and answer the uniform miss."""
        self._log.append("project")
        return None


class _LoggingReader:
    """The real store behind the same shared log, so reads interleave visibly."""

    def __init__(self, store: object, log: list[str]) -> None:
        """Wrap the real store; every read appends to the shared `log`."""
        self._store = store
        self._log = log

    def get_analysis_run(self, run_id: str, owner_id: str | None = None) -> object | None:
        """Record the read, then serve it from the real store unchanged."""
        self._log.append(f"read:{run_id}")
        return self._store.get_analysis_run(run_id, owner_id)  # type: ignore[attr-defined]


def _ordered(
    j: Journey, who: Member, *source_ids: str, view: str = "ExecutiveOverviewView"
) -> list[str]:
    """The interleaved resolve-and-read sequence one request issues."""
    log: list[str] = []
    isolation = IsolationService(j.w.organizations, SqlAccountStore(j.w.factory))
    actions = queries.SemanticQueryActions(
        isolation=_CountingIsolation(isolation, log),  # type: ignore[arg-type]
        sources=_LoggingReader(j.w.store, log),  # type: ignore[arg-type]
        port=_LoggingPort(log),
    )
    actions.request(_query(who, *source_ids, view_id=view))
    return log


def test_one_request_resolves_scope_once_and_before_any_read() -> None:
    """The head of the query shape: authorization first, exactly once."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)

    log = _ordered(j, who, pair.subject_run.run_id, pair.baseline_run.run_id)

    assert log.count("resolve") == 1
    assert log[0] == "resolve"


def test_the_shape_is_one_scoped_read_per_named_source_in_order() -> None:
    """`N` sources, `N` reads, the caller's order, and no source read twice."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    first, second = pair.subject_run.run_id, pair.baseline_run.run_id

    log = _ordered(j, who, first, second)

    assert log == ["resolve", f"read:{first}", f"read:{second}", "project"]


def test_the_shape_over_no_source_and_one_source_completes_the_distribution() -> None:
    """The whole distribution of shapes: zero, one and two named sources.

    Reported as a distribution rather than one sample, which is what makes it a
    baseline. `source_ids` is the only thing the shape varies with.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    one = pair.subject_run.run_id

    assert _ordered(j, who) == ["resolve", "project"]
    assert _ordered(j, who, one) == ["resolve", f"read:{one}", "project"]


def test_a_missing_source_stops_the_reads_where_it_is_found() -> None:
    """The short-circuit is part of the shape: nothing is read after a miss."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    present, absent = pair.subject_run.run_id, "no-such-source"

    log = _ordered(j, who, present, absent, pair.baseline_run.run_id)

    assert log == ["resolve", f"read:{present}", f"read:{absent}"]
    assert "project" not in log


def test_a_missing_source_reaches_no_projection() -> None:
    """A miss costs one read and no projection, which is the cheap path's shape."""
    j = journey()
    who = member(j.w)
    port = _FakePort(None)
    reader = _SpyReader(j.w.store)

    outcome = _actions(j, port, reader).request(_query(who, "no-such-source"))

    assert outcome.kind == ports.KIND_UNAVAILABLE
    assert port.calls == []


def test_the_query_shape_is_identical_for_every_one_of_the_eight_views() -> None:
    """The plan asks for "the query shape each view issues". Every view: the same.

    Not a coincidence to be re-checked per view later -- the orchestration never
    reads the view, so the shape cannot depend on it. Asserted across all eight
    so a view that started reading would be caught here.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    source = pair.subject_run.run_id
    expected = ["resolve", f"read:{source}", "project"]

    shapes = {view_id: _ordered(j, who, source, view=view_id) for view_id in registry.view_ids()}

    assert len(shapes) == 8
    assert all(shape == expected for shape in shapes.values()), shapes


def test_the_projection_half_issues_no_read_at_all() -> None:
    """No module in the RRA package imports anything that could read a source.

    This is why the composed shape equals the orchestration's shape: the RRA half
    is handed its bundle and has no way to fetch another.
    """
    sources = tuple(sorted(_rra_package().glob("*.py")))
    assert len(sources) >= 6, f"the scan found too few files to be scanning anything: {sources}"

    readers = ("sqlalchemy", "requests", "httpx", "socket", "urllib", "sqlite3", "pathlib")
    offenders = [
        f"{path.name}: {name}"
        for path in sources
        for name in sorted(_imports_of(path) & set(readers))
    ]
    assert offenders == [], f"the projection half can reach a source: {offenders}"


def test_the_raw_halves_still_need_the_adapter_between_them() -> None:
    """Formerly the NOT EXERCISED marker. `RCA-007` shipped; this is what remains true.

    Before `RCA-007` this test recorded why no end-to-end baseline existed: the
    real halves, composed by hand with no fake anywhere, refused each other,
    because `SemanticQueryActions` loads `AnalysisRun` rows and `project` admits
    a `RenderableBundle`.

    That refusal is still the correct behaviour and is asserted here still --
    what changed is what it *means*. It no longer records an absence; it records
    that the adapter is load-bearing rather than decorative. Wire the projection
    module straight into the port, as this does, and every request refuses; wire
    `SemanticViewAdapter` in, as `test_the_composed_path_projects_end_to_end`
    does, and it projects. The end-to-end baseline is measured over the composed
    path, not over this one.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    reader = _SpyReader(j.w.store)

    outcome = _actions(j, projection, reader).request(_query(who, pair.subject_run.run_id))

    assert reader.reads == [(pair.subject_run.run_id, who.owner_id)]
    assert outcome.kind == projection.KIND_REFUSED
    assert outcome.refusal == refusals.ViewRefusal(refusals.CAUSE_INCOMPATIBLE_SOURCE_SHAPE)


def test_the_composed_path_projects_end_to_end() -> None:
    """`RCA-007`'s adapter closes the gap `SV1-08` measured.

    The same request as above, with the shipped adapter in the port's place
    instead of the bare projection module. This is the path the end-to-end
    figures in the ledger are measured over.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    adapter = SemanticViewAdapter(SqlFactPackageRepository(j.w.factory))

    outcome = _actions(j, adapter, j.w.store).request(_query(who, pair.subject_run.run_id))

    assert outcome.kind == ports.KIND_ADMITTED
    assert outcome.projection is not None
    assert outcome.projection.rows


def _projection_samples(view_id: str) -> tuple[list[int], tuple[object, ...]]:
    """`_SAMPLES` timings of the real `project`, and every outcome it returned.

    The bundle and the request are built once, outside the loop: building them
    inside would measure the fixture. Nothing is warmed, memoized or reordered --
    the loop calls the same function the product would call, `_SAMPLES` times.
    """
    request = _view(view_id)
    source = _source_for(registry.define_view(view_id))
    timings: list[int] = []
    outcomes: list[object] = []
    for _ in range(_SAMPLES):
        started = time.perf_counter_ns()
        outcomes.append(projection.project(request, (source,)))
        timings.append(time.perf_counter_ns() - started)
    return timings, tuple(outcomes)


def _assert_measured(view_id: str) -> None:
    """A distribution was collected for `view_id`, and every sample agreed.

    The figures themselves are recorded in the dated evidence ledger, not
    asserted: a wall-clock threshold in CI is a flake, and the ledger is where a
    baseline belongs. What is asserted is `FR-144`'s own condition -- that
    measuring changed nothing, so no run of the loop warmed, cached or reordered
    a later one.
    """
    timings, outcomes = _projection_samples(view_id)

    assert len(timings) == _SAMPLES
    assert statistics.median(timings) > 0
    assert all(outcome == outcomes[0] for outcome in outcomes)
    assert outcomes[0].kind == projection.KIND_ADMITTED  # type: ignore[attr-defined]


@pytest.mark.parametrize("view_id", sorted(registry.view_ids()))
def test_the_projection_latency_is_a_measured_distribution(view_id: str) -> None:
    """`FR-144` "may measure execution" -- so it is, for every published view.

    Parametrized over the whole registry rather than over one representative of
    each source shape. The ledger records a distribution per view, and evidence a
    reader cannot regenerate from committed code is not evidence: `_projection_samples`
    is the function that produced every row of that table.
    """
    _assert_measured(view_id)


def _reachable_views() -> dict[str, bool]:
    """Whether each published view can answer non-empty, asked view by view.

    The plan's second risk: "a run that can only produce the null case is NOT
    EXERCISED, not PASS". So each view is driven with a bundle carrying figures
    from its own allowlist, and the answer recorded rather than assumed.
    """
    return {view_id: _answers_non_empty(view_id) for view_id in registry.view_ids()}


def _answers_non_empty(view_id: str) -> bool:
    """One view over a bundle of the shape it admits, carrying a metric it allows."""
    definition = registry.define_view(view_id)
    outcome = projection.project(_view(view_id), (_source_for(definition),))
    return bool(outcome.admitted and outcome.projection and outcome.projection.rows)


def _source_for(definition: contracts.SemanticViewDefinition) -> object:
    """A real bundle of the shape `definition` admits.

    The two-population case is a real `CrossVersionBundle` from `c105_support`,
    not a single-population fixture relabelled: `_shape_of` reads
    `bundle_version`, so a relabelled bundle would answer the shape question
    without answering the projection one.
    """
    if definition.accepted_source_shape == contracts.SHAPE_TWO_POPULATION:
        return _crossversion_bundle()
    return _bundle((_figure(definition.metric_allowlist[0], _EXACT),))


def _crossversion_bundle() -> object:
    """`C1-05`'s real two-population bundle, built from two real packages."""
    return _c105_bundle(build_comparison_request())


def test_the_non_empty_case_is_reachable_for_each_of_the_eight_views() -> None:
    """All eight answer non-empty, so no measurement here is of the null case.

    The plan's second risk asks which views could not be reached. The answer is
    none of them -- but only once `PeriodComparisonView` is driven with the
    two-population bundle `FR-136` binds it to. A first pass here recorded it
    unreachable because the fixture was single-population, which would have
    published a gap that was the fixture's and not the product's.
    """
    reachable = _reachable_views()

    assert len(reachable) == 8
    assert [view for view, ok in reachable.items() if not ok] == []


def test_the_read_path_gained_no_measurement_module() -> None:
    """"Zero additions to any read path" -- the module set is closed, and named.

    This slice ships one test file and one ledger and no source module at all.
    Holding the set here means a timing or caching helper added to either package
    later fails a test rather than arriving unremarked.
    """
    assert {path.stem for path in _rra_package().glob("*.py")} == _RRA_MODULES
    assert {path.stem for path in _rca_package().glob("*.py")} == _RCA_MODULES


def test_no_read_path_module_imports_a_timing_surface() -> None:
    """A module that times itself has changed what it does (`FR-144`)."""
    offenders = [
        f"{path.name}: {name}"
        for path in _read_path_sources()
        for name in sorted(_imports_of(path) & set(_TIMING_MODULES))
    ]
    assert offenders == [], f"the read path measures itself: {offenders}"


def test_no_caching() -> None:
    """`FR-144` bars caching. Nothing on the read path remembers a result.

    `contracts._PUBLISHED_SEMANTICS` is the one piece of module-level mutable
    state, and it is not this: `_claim_identity` stores a definition's semantics
    with `setdefault` and *compares* on every later call, so `define_view` builds
    a fresh definition every time and no call is served from a store. It exists
    for `FR-134`'s immutability, and it makes the second call marginally slower
    rather than faster -- the opposite of a cache.
    """
    assert _offending_names(_CACHING_NAMES) == []


def test_no_pre_aggregation() -> None:
    """`FR-144` bars pre-aggregation. `FR-138`'s scan bars the arithmetic itself."""
    assert _offending_names(_PRE_AGGREGATION_NAMES) == []


def test_no_materialized_views() -> None:
    """`FR-144` bars materialized views. No stored projection stands in front."""
    assert _offending_names(_MATERIALIZED_NAMES) == []


def test_no_sampling() -> None:
    """`FR-144` bars sampling. A view answers over the source or refuses."""
    assert _offending_names(_SAMPLING_NAMES) == []


def test_no_result_changes() -> None:
    """`FR-144` bars result changes: the same request answers the same, always."""
    request = _view()
    bundle = _bundle((_figure("revenue", _EXACT),))

    outcomes = [projection.project(request, (bundle,)) for _ in range(3)]

    assert all(outcome == outcomes[0] for outcome in outcomes)


def test_every_prohibition_has_a_test() -> None:
    """`FR-144`'s five prohibitions, each with a test, checked by name.

    `SV1-07`'s discipline carried forward: a scan cannot find a rule nobody wrote
    down, and no mutant can reach a prohibition that has no test. A sixth clause
    added to `FR-144` and transcribed into `PROHIBITIONS` fails here until it has
    one.
    """
    defined = set(globals())

    missing = [name for name in PROHIBITIONS if f"test_no_{name}" not in defined]

    assert len(PROHIBITIONS) == 5
    assert missing == [], f"transcribed from FR-144 but never tested: {missing}"
