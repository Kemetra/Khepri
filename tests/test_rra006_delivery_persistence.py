from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.artifact_persistence import SqlArtifactRepository, StoredArtifact
from khepri.rra.bundle import (
    LANGUAGE_DIRECTION,
    NARRATIVE_INCLUDED,
    REQUIRED_SURFACES,
    SURFACE_WEB,
    ReportBundle,
    StatedFigure,
    SurfaceContent,
    SurfaceLanguage,
)
from khepri.rra.delivery_persistence import (
    DeliveryConflict,
    DeliveryCorrupted,
    ReportDeliveryRow,
    ReportDeliverySurfaceRow,
    SqlDeliveryStore,
    surface_digest,
)
from khepri.rra.facts import AdmittedInput, FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.jobs import EnqueueJob, LeaseRequest, ReportJob
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    LanguageNarrative,
    NarrativeDraft,
    NarrativeRequest,
    NarrativeSection,
)
from khepri.rra.package_source import (
    SessionFactPackageSource,
    SessionPackageReader,
    rebuild_fact_package,
)
from khepri.rra.packages import FactPackageRecord, FactPackageService, PackageCorrupted
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.pipeline import (
    DeliveryRecord,
    ReportDelivery,
    ReportPipeline,
    ReportPipelinePorts,
    ReportPublication,
)
from khepri.rra.profiling import build_profile
from khepri.rra.report_artifacts import (
    ARTIFACT_METADATA,
    SURFACE_ARTIFACT_KINDS,
    ArtifactPayload,
    MaterializedSurface,
)
from khepri.rra.sessions import (
    BetaSession,
    CrossSessionAccessDenied,
    InvitationService,
    SessionExpired,
    SessionScope,
)
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    published_mapping_identity,
)

NOW = datetime(2026, 7, 30, 16, 0, tzinfo=UTC)
ADAPTER_VERSION = "test.adapter.v1"
IDEMPOTENCY_KEY = "b" * 64
# The size a stand-in renderer reports. No surface here writes a payload.
SURFACE_SIZE = 1024

GOLDEN = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)

# Customer text the golden dataset carries. Nothing a delivery record stores may
# be spelled from it: RRA-007 requires operational evidence to hold no source
# content, safe labels, or narrative.
CONTENT = ("Beverages", "Snacks", "Cairo", "Giza", "INV-1", "125.50", "500.00")


def package(content: bytes = GOLDEN) -> FactPackage:
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    # Built under the published mapping identity: this module's subject is not
    # the version gate, so its packages must keep combining a triple
    # `versions.ADMITTED_PACKAGE_PAIRS` admits. The whole build sits inside the
    # block because `facts._assert_derived_from_profile` re-derives the mapping
    # and compares it by value, so restamping the object afterwards would fail
    # that provenance guard instead.
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        return build_fact_package(
            AdmittedInput(
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            ),
        )


def stored(
    built: FactPackage,
    *,
    scope: SessionScope,
    document: dict[str, object] | None = None,
) -> FactPackageRecord:
    """A published package row, as the RRA-004 repository hands one back."""
    return FactPackageRecord(
        package_id="fct_alpha",
        owner_id=scope.owner_id,
        session_id=scope.session_id,
        profile_id="prf_alpha",
        package_version=built.package_version,
        formula_version=built.formula_version,
        mapping_version=built.mapping_version,
        profile_document_digest="c" * 64,
        source_sha256_hex=built.source_sha256_hex,
        package_digest=built.digest,
        row_count=built.row_count,
        created_at=NOW,
        # Through JSON and back, because that is the only shape a stored
        # document ever arrives in.
        document=json.loads(json.dumps(document or built.as_document())),
    )


# --- fakes ----------------------------------------------------------------


class Published:
    """A reader of published packages, as `FactPackageService` presents one."""

    def __init__(
        self,
        record: FactPackageRecord | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self._record = record
        self._error = error
        self.asked: list[tuple[str, datetime]] = []

    def get_session_package(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> FactPackageRecord | None:
        self.asked.append((session_id, now))
        if self._error is not None:
            raise self._error
        return self._record


class Adapter:
    """A provider that cites the revenue fact it was actually given."""

    @property
    def adapter_version(self) -> str:
        return ADAPTER_VERSION

    def draft(self, request: NarrativeRequest, *, timeout_seconds: Decimal) -> NarrativeDraft:
        fact_id = next(
            str(entry["fact_id"])
            for entry in request.document["facts"]
            if entry["metric"] == "revenue"
        )
        return NarrativeDraft(
            adapter_version=ADAPTER_VERSION,
            request_digest=request.digest,
            languages=(
                LanguageNarrative(
                    language=LANGUAGE_ARABIC,
                    sections=(
                        NarrativeSection(
                            section_id="summary",
                            text="بلغت الإيرادات ٥٠٠٫٠٠.",
                            cited_fact_ids=(fact_id,),
                            caveats=(),
                        ),
                    ),
                ),
                LanguageNarrative(
                    language=LANGUAGE_ENGLISH,
                    sections=(
                        NarrativeSection(
                            section_id="summary",
                            text="Revenue was 500.00.",
                            cited_fact_ids=(fact_id,),
                            caveats=(),
                        ),
                    ),
                ),
            ),
        )


def surface_of(bundle: ReportBundle, surface: str) -> SurfaceContent:
    return SurfaceContent(
        surface=surface,
        bundle_id=bundle.bundle_id,
        output_size_bytes=SURFACE_SIZE,
        languages=tuple(
            SurfaceLanguage(
                language=language,
                direction=LANGUAGE_DIRECTION[language],
                sections=bundle.section_ids,
                stated=tuple(
                    StatedFigure(
                        figure_id=entry.figure_id,
                        text=entry.renderings[language],
                        section=entry.section,
                    )
                    for entry in bundle.figures
                ),
                caveats=bundle.caveats,
                disclosure=bundle.disclosure(language),
            )
            for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)
        ),
    )


class Renderer:
    def __init__(self, surface: str) -> None:
        self._surface = surface

    @property
    def surface(self) -> str:
        return self._surface

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        return surface_of(bundle, self._surface)

    def render_materialized(self, bundle: ReportBundle) -> MaterializedSurface:
        kinds = SURFACE_ARTIFACT_KINDS[self.surface]
        final_size = SURFACE_SIZE - len(kinds) + 1
        artifacts = tuple(
            ArtifactPayload.of(
                kind=kind,
                media_type=ARTIFACT_METADATA[kind][0],
                file_name=ARTIFACT_METADATA[kind][1],
                content=b"x" if index < len(kinds) - 1 else b"x" * final_size,
            )
            for index, kind in enumerate(kinds)
        )
        return MaterializedSurface(content=self.render(bundle), artifacts=artifacts)


class Execution:
    def __init__(self, leased: ReportJob) -> None:
        self.job = leased
        self.beats = 0

    def heartbeat(self) -> ReportJob:
        self.beats += 1
        return self.job


class Trap:
    """A session that refuses one write, part-way through a transaction."""

    def __init__(self, database: Session, *, refuse_at: int) -> None:
        self._database = database
        self._refuse_at = refuse_at
        self.adds = 0

    def add(self, instance: object) -> None:
        self.adds += 1
        if self.adds == self._refuse_at:
            raise RuntimeError("The delivery write failed part-way through.")
        self._database.add(instance)

    def __getattr__(self, name: str) -> object:
        return getattr(self._database, name)


class TrapBegin:
    def __init__(self, inner: object, *, refuse_at: int) -> None:
        self._inner = inner
        self._refuse_at = refuse_at

    def __enter__(self) -> Trap:
        return Trap(self._inner.__enter__(), refuse_at=self._refuse_at)

    def __exit__(self, *details: object) -> object:
        return self._inner.__exit__(*details)


class TrapFactory:
    """The real factory, with one transaction rigged to fail mid-write."""

    def __init__(self, factory: sessionmaker[Session], *, refuse_at: int) -> None:
        self._factory = factory
        self._refuse_at = refuse_at

    def begin(self) -> TrapBegin:
        return TrapBegin(self._factory.begin(), refuse_at=self._refuse_at)

    def __call__(self) -> Session:
        return self._factory()


# --- harness --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Harness:
    factory: sessionmaker[Session]
    session: BetaSession
    jobs: SqlReportJobRepository
    store: SqlDeliveryStore

    @property
    def scope(self) -> SessionScope:
        return SessionScope(
            owner_id=self.session.owner_id,
            session_id=self.session.session_id,
        )

    def leased(self, job_id: str = "job_alpha", key: str = IDEMPOTENCY_KEY) -> ReportJob:
        self.jobs.enqueue(
            EnqueueJob(
                scope=self.scope,
                job_id=job_id,
                idempotency_key=key,
                queued_at=NOW,
                max_attempts=3,
            )
        )
        leased = self.jobs.lease(
            LeaseRequest(
                job_id=job_id,
                worker_id="worker_alpha",
                now=NOW,
                lease_for=timedelta(minutes=5),
            )
        )
        assert leased is not None
        return leased

    def delivery(
        self,
        leased: ReportJob,
        *,
        built: FactPackage | None = None,
        session_id: str | None = None,
    ) -> ReportDelivery:
        source = built or package()
        bundle = ReportBundle.of(source, narrative=_narrative_for(source))
        surfaces = tuple(surface_of(bundle, name) for name in REQUIRED_SURFACES)
        record = DeliveryRecord(
            job_id=leased.job_id,
            session_id=session_id or leased.session_id,
            bundle_id=bundle.bundle_id,
            package_version=bundle.identity.package_version,
            narrative_state=NARRATIVE_INCLUDED,
            surfaces=REQUIRED_SURFACES,
        )
        return ReportDelivery(record=record, bundle=bundle, surfaces=surfaces)

    def rows(self) -> list[ReportDeliveryRow]:
        with self.factory() as database:
            return list(database.scalars(select(ReportDeliveryRow)))

    def surface_rows(self) -> list[ReportDeliverySurfaceRow]:
        with self.factory() as database:
            return list(database.scalars(select(ReportDeliverySurfaceRow)))


def _narrative_for(built: FactPackage) -> NarrativeDraft:
    return Adapter().draft(
        NarrativeRequest.of(built, adapter_version=ADAPTER_VERSION),
        timeout_seconds=Decimal(1),
    )


def harness(*, now: datetime = NOW) -> Harness:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    sessions = SqlSessionStore(factory)
    invitations = InvitationService(sessions)
    beta_session = invitations.redeem(
        invitations.issue_invitation(expires_at=NOW + timedelta(hours=1)),
        now=NOW,
    )
    return Harness(
        factory=factory,
        session=beta_session,
        jobs=SqlReportJobRepository(factory),
        store=SqlDeliveryStore(factory, now=lambda: now),
    )


def source_for(
    record: FactPackageRecord | None,
    *,
    error: Exception | None = None,
) -> tuple[SessionFactPackageSource, Published]:
    published = Published(record, error=error)
    return (
        SessionFactPackageSource(packages=published, now=lambda: NOW),
        published,
    )


# --- rebuilding a package from its stored document -------------------------


def test_a_stored_document_rebuilds_the_package_it_was_published_from() -> None:
    # RRA-004 makes the package the only numerical source for every surface, so
    # a report generated from a stored document must be generated from the same
    # facts, series, comparisons, refusals and caveats as the first run.
    built = package()

    rebuilt = rebuild_fact_package(json.loads(json.dumps(built.as_document())))

    assert rebuilt == built
    assert rebuilt.digest == built.digest


def test_a_rebuilt_package_carries_every_citable_figure() -> None:
    built = package()

    rebuilt = rebuild_fact_package(built.as_document())

    assert rebuilt.citation_ids == built.citation_ids
    assert rebuilt.value("revenue") == "500.00"
    assert rebuilt.trend() is not None
    assert rebuilt.comparison("category") is not None
    assert rebuilt.refusals == built.refusals


def test_a_package_source_loads_the_published_package_for_a_leased_job() -> None:
    test = harness()
    leased = test.leased()
    built = package()
    source, published = source_for(stored(built, scope=test.scope))

    loaded = source.load(leased)

    assert loaded == built
    assert published.asked == [(leased.session_id, NOW)]


def test_a_document_that_no_longer_hashes_to_its_address_is_refused() -> None:
    # The digest is what makes a stored package citable: a document that does
    # not hash to its recorded address would publish altered figures under an
    # address that vouches for the originals. The altered value still parses, so
    # the recomputed content address is the only thing that can catch it.
    test = harness()
    leased = test.leased()
    built = package()
    document = built.as_document()
    facts = list(document["facts"])
    document["facts"] = [
        {**entry, "value": "125.51"} if entry["metric"] == "revenue" else entry
        for entry in facts
    ]
    source, _ = source_for(stored(built, scope=test.scope, document=document))

    with pytest.raises(PackageCorrupted):
        source.load(leased)


def test_a_document_missing_a_governed_field_is_refused() -> None:
    test = harness()
    leased = test.leased()
    built = package()
    document = built.as_document()
    del document["monetary_precision"]
    source, _ = source_for(stored(built, scope=test.scope, document=document))

    with pytest.raises(PackageCorrupted):
        source.load(leased)


def test_a_job_cannot_reach_a_package_belonging_to_another_owner() -> None:
    # The source is keyed by the whole job rather than by a session identifier
    # precisely so this check is possible: the reader selects on the session
    # alone, and a bare session string does not carry the owner.
    test = harness()
    leased = test.leased()
    intruder = SessionScope(owner_id="own_other", session_id=leased.session_id)
    source, _ = source_for(stored(package(), scope=intruder))

    with pytest.raises(CrossSessionAccessDenied):
        source.load(leased)


def test_a_session_with_no_published_package_loads_nothing() -> None:
    test = harness()
    leased = test.leased()
    source, _ = source_for(None)

    assert source.load(leased) is None


def test_an_unavailable_session_refuses_rather_than_reporting_no_package() -> None:
    # `None` means "no package was published for this session", which the
    # pipeline reports as a missing package. An expired or deleted session is a
    # different fact, and flattening it into `None` would report a boundary
    # violation as an ordinary absence.
    test = harness()
    leased = test.leased()
    source, _ = source_for(None, error=SessionExpired("Session content has expired."))

    with pytest.raises(SessionExpired):
        source.load(leased)


def test_the_fact_package_service_reads_packages_the_way_the_source_asks() -> None:
    # The source delegates every governed check -- session, consent, expiry,
    # superseded versions, profile provenance -- to the RRA-004 service rather
    # than restating them, so the service has to satisfy the reader it needs.
    service = FactPackageService(
        sessions=SqlSessionStore(sessionmaker(create_engine("sqlite+pysqlite://"))),
        uploads=None,  # type: ignore[arg-type]
        objects=None,  # type: ignore[arg-type]
        profiles=None,  # type: ignore[arg-type]
        packages=None,  # type: ignore[arg-type]
    )

    assert isinstance(service, SessionPackageReader)


# --- delivering one whole report ------------------------------------------


def test_a_delivered_report_is_found_by_the_job_that_produced_it() -> None:
    test = harness()
    leased = test.leased()
    delivery = test.delivery(leased)

    written = test.store.deliver(delivery)
    found = test.store.find_delivery(leased.job_id)

    assert written == delivery.record
    assert found == delivery.record
    assert found is not None
    assert found.surfaces == REQUIRED_SURFACES


def test_a_job_that_delivered_nothing_answers_the_idempotency_question() -> None:
    test = harness()
    test.leased()

    assert test.store.find_delivery("job_alpha") is None


def test_the_store_stamps_the_generation_time_and_inherits_the_expiry() -> None:
    # RRA-006 binds a generation timestamp to a bundle and stores published
    # outputs under the same expiry boundary as the input. Neither is in the
    # bundle's identity, so both belong to the record -- and the store is what
    # holds a clock.
    generated = NOW + timedelta(minutes=7)
    test = harness(now=generated)
    leased = test.leased()

    test.store.deliver(test.delivery(leased))

    row = test.rows()[0]
    assert row.generated_at.replace(tzinfo=UTC) == generated
    assert row.expires_at.replace(tzinfo=UTC) == test.session.content_expires_at


def test_delivering_one_job_twice_returns_the_record_already_written() -> None:
    test = harness()
    leased = test.leased()
    delivery = test.delivery(leased)

    first = test.store.deliver(delivery)
    second = test.store.deliver(delivery)

    assert second == first
    assert len(test.rows()) == 1
    assert len(test.surface_rows()) == len(REQUIRED_SURFACES)


def test_a_second_delivery_naming_another_bundle_is_refused() -> None:
    # RRA-006 forbids serving a mixture of versions. One job that has already
    # delivered a report cannot deliver a different one over it, and the store
    # refuses rather than choosing which of the two a reader gets.
    test = harness()
    leased = test.leased()
    test.store.deliver(test.delivery(leased))
    other = test.delivery(leased, built=package(GOLDEN.replace(b"90.00", b"91.00")))

    with pytest.raises(DeliveryConflict):
        test.store.deliver(other)

    assert len(test.rows()) == 1


def test_a_failure_between_surfaces_leaves_no_delivery_observable() -> None:
    # The whole report is one unit. A store that committed the record and then
    # failed on a surface would leave a delivery naming three surfaces beside
    # fewer than three, which is the partial export RRA-006 calls an incomplete
    # bundle rather than a delivery.
    test = harness()
    leased = test.leased()
    trapped = SqlDeliveryStore(
        TrapFactory(test.factory, refuse_at=3),  # type: ignore[arg-type]
        now=lambda: NOW,
    )

    with pytest.raises(RuntimeError, match="part-way"):
        trapped.deliver(test.delivery(leased))

    assert test.store.find_delivery(leased.job_id) is None
    assert test.rows() == []
    assert test.surface_rows() == []


def test_a_delivery_naming_another_sessions_job_is_refused() -> None:
    test = harness()
    leased = test.leased()
    delivery = test.delivery(leased, session_id="ses_other")

    with pytest.raises(CrossSessionAccessDenied):
        test.store.deliver(delivery)

    assert test.rows() == []


def test_a_delivery_for_an_unknown_job_is_refused() -> None:
    test = harness()
    leased = test.leased()
    unknown = replace(leased, job_id="job_missing")

    with pytest.raises(CrossSessionAccessDenied):
        test.store.deliver(test.delivery(unknown))


def test_a_delivery_after_the_session_boundary_has_passed_is_refused() -> None:
    # Published outputs inherit the input's expiry, so there is no boundary left
    # to publish into once it has passed.
    test = harness(now=NOW + timedelta(days=8))
    leased = test.leased()

    with pytest.raises(SessionExpired):
        test.store.deliver(test.delivery(leased))

    assert test.rows() == []


def test_a_delivery_missing_a_surface_row_is_refused_on_read() -> None:
    test = harness()
    leased = test.leased()
    test.store.deliver(test.delivery(leased))
    with test.factory.begin() as database:
        database.execute(
            delete(ReportDeliverySurfaceRow).where(
                ReportDeliverySurfaceRow.surface == SURFACE_WEB
            )
        )

    with pytest.raises(DeliveryCorrupted):
        test.store.find_delivery(leased.job_id)


def test_every_surface_is_recorded_by_digest_rather_than_by_content() -> None:
    # RRA-007 requires operational evidence that logs no source content, safe
    # labels, or narrative. A digest over what a surface presented is enough to
    # tell two runs apart without storing a word of either.
    test = harness()
    leased = test.leased()
    delivery = test.delivery(leased)

    test.store.deliver(delivery)

    recorded = test.store.find_surfaces(leased.job_id)
    assert [entry.surface for entry in recorded] == list(REQUIRED_SURFACES)
    assert [entry.content_digest for entry in recorded] == [
        surface_digest(entry) for entry in delivery.surfaces
    ]
    assert {entry.bundle_id for entry in recorded} == {delivery.bundle.bundle_id}
    written = " ".join(
        str(value)
        for row in (*test.rows(), *test.surface_rows())
        for value in row.__dict__.values()
    )
    assert not [text for text in CONTENT if text in written]


def test_a_surface_that_weighed_more_presented_the_same_report() -> None:
    # The digest is over what a surface presented, and a byte count is a
    # property of the file rather than of the report. A PDF whose metadata grew
    # between two runs must still be recognizable as the same presentation, or
    # deterministic regeneration stops being checkable from the evidence.
    source = package()
    content = surface_of(ReportBundle.of(source, narrative=_narrative_for(source)), SURFACE_WEB)

    heavier = replace(content, output_size_bytes=content.output_size_bytes + 1)

    assert surface_digest(heavier) == surface_digest(content)


def test_two_runs_over_the_same_report_record_the_same_surface_digests() -> None:
    # Deterministic regeneration reaches the evidence too: the same package and
    # narrative produce the same surfaces, so a retry is recognizable as the
    # same report rather than a new one.
    first = harness()
    second = harness()
    original = first.delivery(first.leased())
    repeat = second.delivery(second.leased())

    first.store.deliver(original)
    second.store.deliver(repeat)

    assert [entry.content_digest for entry in first.store.find_surfaces("job_alpha")] == [
        entry.content_digest for entry in second.store.find_surfaces("job_alpha")
    ]


# --- both ports, under the pipeline that needs them ------------------------


def test_the_pipeline_runs_one_leased_job_against_the_stored_ports() -> None:
    # The gap this closes: `ReportPipeline` had two Protocols and no
    # implementation of either, so it could not be constructed outside a test.
    test = harness()
    leased = test.leased()
    source, _ = source_for(stored(package(), scope=test.scope))
    repository = SqlArtifactRepository(test.factory)

    class Publisher:
        def find_delivery(self, job_id: str) -> DeliveryRecord | None:
            return test.store.find_delivery(job_id)

        def publish(self, publication: ReportPublication) -> DeliveryRecord:
            artifacts = tuple(
                StoredArtifact(
                    job_id=publication.delivery.record.job_id,
                    artifact_kind=payload.kind,
                    owner_id=test.session.owner_id,
                    session_id=test.session.session_id,
                    bundle_id=publication.delivery.record.bundle_id,
                    object_key=f"reports/{publication.delivery.record.bundle_id}/{payload.kind}",
                    media_type=payload.media_type,
                    file_name=payload.file_name,
                    size_bytes=len(payload.content),
                    sha256_hex=payload.sha256_hex,
                    created_at=NOW,
                    expires_at=test.session.content_expires_at,
                    encryption_algorithm="AES-256-GCM",
                    envelope_version=1,
                    ciphertext_sha256_hex="c" * 64,
                )
                for payload in publication.artifacts
            )
            boundary = repository.boundary(publication, created_at=NOW)
            return repository.commit(
                publication,
                artifacts,
                boundary=boundary,
                committed_at=NOW,
            )

    pipeline = ReportPipeline(
        ports=ReportPipelinePorts(
            packages=source,
            adapter=Adapter(),
            renderers=tuple(Renderer(name) for name in REQUIRED_SURFACES),
            deliveries=Publisher(),
        ),
        monotonic_ms=lambda: 0,
    )

    outcome = pipeline.run(Execution(leased))
    repeated = pipeline.run(Execution(leased))

    assert outcome.delivered is True
    assert outcome.record.surfaces == REQUIRED_SURFACES
    assert outcome.record.narrative_state == NARRATIVE_INCLUDED
    assert repeated.delivered is False
    assert repeated.record == outcome.record
    assert len(test.rows()) == 1
def test_a_package_stored_before_the_basket_input_still_rebuilds() -> None:
    """`sale_units_total` was added without moving `PACKAGE_VERSION`.

    Documents persisted before it exists carry no such key, and
    `package_source._required` refuses a missing key even in optional mode --
    so a reader that only tolerated a null value would strand every package
    published before the field. An absent basket input rebuilds as `None`,
    which is what it means: not counted, rather than counted and zero.
    """
    built = package()
    stored = json.loads(json.dumps(built.as_document()))
    legacy = {
        key: value for key, value in stored.items() if key != 'sale_units_total'
    }
    assert 'sale_units_total' not in legacy

    rebuilt = rebuild_fact_package(legacy)

    assert rebuilt.sale_units_total is None
    # And everything else about the stored package is unchanged.
    assert rebuilt.facts == built.facts
    assert rebuilt.row_count == built.row_count
def test_a_legacy_package_document_still_matches_its_stored_digest() -> None:
    """The readback is only half: the rebuilt package must re-digest the same.

    `SessionFactPackageSource.load` compares `package.digest` against the stored
    `package_digest`. A document written before `sale_units_total` existed omits
    the key; if `as_document()` then emits it, the rebuilt digest differs and a
    validly stored package is refused as corrupt -- the same shape as the
    coverage-manifest round trip this branch opened with. Raised in review.
    """
    built = package()
    stored = json.loads(json.dumps(built.as_document()))
    legacy = {
        key: value for key, value in stored.items() if key != 'sale_units_total'
    }
    assert 'sale_units_total' not in legacy

    rebuilt = rebuild_fact_package(legacy)

    assert rebuilt.sale_units_total is None
    # `digest` hashes `as_document()`, so this is the round trip the digest
    # comparison in `SessionFactPackageSource.load` actually performs.
    assert rebuilt.as_document() == legacy, (
        'the rebuilt package does not serialize back to the document it came '
        'from, so its digest differs and a stored legacy package is refused '
        'as corrupt'
    )
def test_an_incomplete_dimension_survives_the_package_round_trip() -> None:
    """`incomplete_values` was serialized and never read back.

    `package_source._comparison` constructed `Comparison` without it, so every
    package holding an incomplete dimension rebuilt with the dataclass default
    `False` and re-digested differently -- and `SessionFactPackageSource.load`
    refused exactly the packages the flag was added to handle. Found in review.
    """
    content = (
        b"date,revenue,units,invoice_no,product\n"
        b"2026-01-05,100.00,3,INV-1,Water\n"
        b"2026-01-06,200.00,5,INV-2,\n"
    )
    built = package(content)
    published = built.comparison('product')
    assert published is not None
    # The premise: this package really does carry an incomplete dimension.
    assert published.comparison.incomplete_values

    rebuilt = rebuild_fact_package(json.loads(json.dumps(built.as_document())))

    assert rebuilt.comparison('product').comparison.incomplete_values
    assert rebuilt.digest == built.digest, (
        'the rebuilt package re-digests differently, so delivery refuses it'
    )
