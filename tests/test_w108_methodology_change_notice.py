"""`W1-08` -- the Methodology Change Notice (`RCA-005` `FR-116`; blueprint §7.4).

Where a later run's governed versions -- the mapping its data was admitted under, the package and
the formula it was derived with -- differ from the previous completed run's, Analysis detail says
so, names each identifier that changed, reaches the previous analysis, and states that figures from
the two are not numerically comparable. It presents the *difference* and computes nothing: no delta,
no percentage, no "up from", and no figure from either run.

The governed versions the real pipeline publishes today are one triple, so a difference cannot be
produced through the journey; these cases shape the records directly, as the spine's tests do, and
the two cases that can run end to end -- one run, and two runs of one file -- do so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.organizations import Organization
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.contracts import (
    RUN_COMPLETED,
    RUN_STARTED,
    AdmittedSource,
    AnalysisRun,
    ArtifactBinding,
    DatasetVersion,
    PublishedArtifact,
    RunOutcome,
    RunSubject,
    VersionLifecycle,
)
from khepri.rca.workspace.persistence import WorkspaceHistory
from khepri.rca.workspace.tombstones import SectionStates
from khepri.rra.bundle import ORDERED_SECTIONS
from khepri.rra.rendering.wording import COMPONENT_CHROME, SECTION_HEADINGS
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_copy import SHELL_COPY
from khepri.runtime.shell_provenance import Provenance
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w106_support import completed_run, detail_address, page

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
EARLIER = NOW - timedelta(days=3)
ORGANIZATION = "org-acme"
SCOPE = "scope-acme"
DIGEST = "d" * 64
EN = SHELL_COPY["en"]


# --- records shaped directly ----------------------------------------------------------------------


@dataclass
class _Context:
    account_id: str
    organization_id: str | None
    role: str | None = "owner"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


class _StubResolver:
    def for_request(self, token: str, *, organization_id: str | None, now: object) -> _Context:
        return _Context("acct-a", ORGANIZATION)

    def require_owner(self, token: str, *, organization_id: str, now: object) -> _Context:
        return _Context("acct-a", ORGANIZATION)


class _StubOrganizations:
    def organizations_for_account(self, account_id: str) -> list[Organization]:
        return [
            Organization._from_storage(organization_id=ORGANIZATION, name="Acme", created_at=NOW)
        ]

    def memberships_for_organization(self, organization_id: str) -> list[object]:
        return []


class _StubIsolation:
    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        return SCOPE


class _StubBridge:
    def open(self, **kwargs: object) -> object:  # pragma: no cover
        raise AssertionError

    def resume(self, **kwargs: object) -> object:  # pragma: no cover
        raise AssertionError


@dataclass
class _StubRecords:
    versions: tuple[DatasetVersion, ...] = ()
    runs: tuple[AnalysisRun, ...] = ()
    bindings: tuple[ArtifactBinding, ...] = ()

    def history_for_scope(self, owner_id: str) -> WorkspaceHistory:
        return WorkspaceHistory(
            versions=self.versions, runs=self.runs, bindings=self.bindings, tombstones=()
        )


@dataclass
class _StubProvenance:
    """A Passport per run, with the section outcomes each run retained."""

    outcomes: dict[str, SectionStates] = field(default_factory=dict)

    def for_run(self, owner_id: str, run: object, version: object) -> Provenance | None:
        if run.state != RUN_COMPLETED:
            return None
        return Provenance(
            session_id=f"ses-{run.run_id}",
            job_id=f"job-{run.run_id}",
            covered_start=NOW.date(),
            covered_end=NOW.date(),
            timezone="Africa/Cairo",
            aggregate_scope=None,
            attested_by="Operator",
            row_count=4,
            sections=self.outcomes.get(run.run_id, _sections()),
            reachable=True,
        )


def _version(version_id: str, mapping: str, *, created_at: datetime = EARLIER) -> DatasetVersion:
    return DatasetVersion._from_storage(
        version_id=version_id,
        owner_id=SCOPE,
        source=AdmittedSource(
            plaintext_digest=DIGEST,
            ciphertext_digest=DIGEST,
            size_bytes=4096,
            media_type="text/csv",
            manifest_digest=DIGEST,
            mapping_version=mapping,
            admission_outcome="admitted",
        ),
        lifecycle=VersionLifecycle(created_at=created_at, sealed_at=created_at),
    )


def _run(
    run_id: str,
    version_id: str,
    *,
    started_at: datetime,
    package: str = "rra004.package.v3",
    formula: str = "rra004.formula.v2",
    state: str = RUN_COMPLETED,
) -> AnalysisRun:
    outcome = (
        RunOutcome(
            state=state,
            package_digest=DIGEST,
            package_version=package,
            formula_version=formula,
            completed_at=started_at,
        )
        if state == RUN_COMPLETED
        else RunOutcome(state=state)
    )
    return AnalysisRun._from_storage(
        subject=RunSubject(run_id=run_id, owner_id=SCOPE, version_id=version_id),
        outcome=outcome,
        started_at=started_at,
    )


def _bindings(*run_ids: str) -> tuple[ArtifactBinding, ...]:
    return tuple(
        ArtifactBinding._from_storage(
            run_id=run_id,
            owner_id=SCOPE,
            artifact=PublishedArtifact(surface=kind, artifact_digest=DIGEST),
            published_at=NOW,
        )
        for run_id in run_ids
        for kind in REQUIRED_ARTIFACT_KINDS
    )


def _sections(*refused: str) -> SectionStates:
    return SectionStates(
        **{s: ("refused" if s in refused else "answered") for s in ORDERED_SECTIONS}
    )


def _shell(records: _StubRecords, provenance: _StubProvenance) -> TestClient:
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(),
            organizations=_StubOrganizations(),
            records=records,
            isolation=_StubIsolation(),
            bridge=_StubBridge(),
            provenance=provenance,
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def _detail(
    records: _StubRecords, provenance: _StubProvenance, run_id: str, language: str = "en"
) -> str:
    address = f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/analyses/{run_id}"
    return _shell(records, provenance).get(address).text


def _notice(html: str) -> str:
    start = html.index('class="change-notice"')
    return html[start : html.index("</section>", start)]


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _two_runs(
    *,
    later_mapping: str = "rra003.mapping.v3",
    later_package: str = "rra004.package.v3",
    later_formula: str = "rra004.formula.v2",
) -> _StubRecords:
    """An earlier run under the v2 triple, and a later one under whatever the case names."""
    return _StubRecords(
        versions=(
            _version("ver-b", later_mapping, created_at=NOW - timedelta(days=1)),
            _version("ver-a", "rra003.mapping.v2"),
        ),
        runs=(
            _run("run-b", "ver-b", started_at=NOW, package=later_package, formula=later_formula),
            _run(
                "run-a",
                "ver-a",
                started_at=EARLIER,
                package="rra004.package.v2",
                formula="rra004.formula.v1",
            ),
        ),
        bindings=_bindings("run-a", "run-b"),
    )


# --- FR-116: the Notice, when governed versions differ --------------------------------------------


@pytest.mark.parametrize("language", ["en", "ar"])
def test_a_later_run_under_other_versions_carries_the_notice_and_names_each_change(
    language: str,
) -> None:
    html = _detail(_two_runs(), _StubProvenance(), "run-b", language)

    copy = SHELL_COPY[language]
    notice = _notice(html)
    assert copy["notice_title"] in notice
    # Each governed identifier that differs, earlier then later, reachable in the Notice itself.
    for label, earlier, later in (
        (copy["notice_mapping"], "rra003.mapping.v2", "rra003.mapping.v3"),
        (copy["notice_package"], "rra004.package.v2", "rra004.package.v3"),
        (copy["notice_formula"], "rra004.formula.v1", "rra004.formula.v2"),
    ):
        assert label in notice, label
        assert notice.index(earlier) < notice.index(later), label
    # The previous analysis is reachable, and the incomparability is stated, not implied.
    assert f'href="{SHELL_PREFIX}/{language}/{ORGANIZATION}/analyses/run-a"' in notice
    assert copy["notice_not_comparable"] in notice


def test_only_the_identifiers_that_differ_are_named() -> None:
    records = _two_runs(later_mapping="rra003.mapping.v2", later_package="rra004.package.v2")

    notice = _notice(_detail(records, _StubProvenance(), "run-b"))

    assert EN["notice_formula"] in notice
    assert EN["notice_mapping"] not in notice and EN["notice_package"] not in notice


def test_the_notice_presents_no_figure_delta_or_comparison_word() -> None:
    """`FR-116`: the difference, never a comparison. No digit but the version identifiers' own, no
    percent sign, and none of the words that would read as a numeric comparison."""
    notice = _text(_notice(_detail(_two_runs(), _StubProvenance(), "run-b")))

    stripped = re.sub(r"rra00\d\.[a-z]+\.v\d", "", notice)
    assert not re.search(r"\d", stripped), stripped
    assert "%" not in notice
    for word in ("up from", "down from", "increase", "decrease", "higher", "lower"):
        assert word not in notice.lower(), word


def test_availability_that_changed_between_the_two_runs_is_named_in_the_reports_words() -> None:
    """The roadmap's `W1-08` names refusals among what changed. A section the earlier run answered
    and the later refused is listed, in the report's section heading and quality words."""
    provenance = _StubProvenance(
        outcomes={"run-a": _sections(), "run-b": _sections("comparison", "growth")}
    )

    notice = _notice(_detail(_two_runs(), provenance, "run-b"))

    chrome = COMPONENT_CHROME["en"]
    assert EN["notice_availability"] in notice
    for section in ("comparison", "growth"):
        assert SECTION_HEADINGS["en"][section] in notice, section
    assert chrome["quality_answered"] in notice and chrome["quality_refused"] in notice
    assert SECTION_HEADINGS["en"]["overview"] not in notice


def test_availability_alone_raises_no_notice() -> None:
    """Refusals that change under one methodology are a property of the data, not of the method;
    `FR-116` is about governed versions. Without a version difference there is no Notice."""
    records = _two_runs(
        later_mapping="rra003.mapping.v2",
        later_package="rra004.package.v2",
        later_formula="rra004.formula.v1",
    )
    provenance = _StubProvenance(outcomes={"run-a": _sections(), "run-b": _sections("growth")})

    html = _detail(records, provenance, "run-b")

    assert 'class="change-notice"' not in html
    assert EN["notice_title"] not in html


def test_the_earlier_run_carries_no_notice_about_a_later_one() -> None:
    """The Notice reads backward only: the later run tells the customer what changed since the
    previous one. The earlier run stood on its own methodology when it ran."""
    html = _detail(_two_runs(), _StubProvenance(), "run-a")

    assert 'class="change-notice"' not in html


def test_the_previous_run_is_the_latest_completed_one_over_the_same_data_where_one_exists() -> None:
    """`FR-116`: "the same or a related dataset version". The same version wins where an earlier
    completed run over it exists; a started or failed run is not a methodology to compare
    against."""
    records = _StubRecords(
        versions=(
            _version("ver-b", "rra003.mapping.v3", created_at=NOW - timedelta(days=1)),
            _version("ver-a", "rra003.mapping.v2"),
        ),
        runs=(
            _run("run-c", "ver-b", started_at=NOW),
            _run("run-x", "ver-b", started_at=NOW - timedelta(hours=1), state=RUN_STARTED),
            _run(
                "run-b",
                "ver-b",
                started_at=NOW - timedelta(hours=2),
                package="rra004.package.v2",
                formula="rra004.formula.v1",
            ),
            _run(
                "run-a",
                "ver-a",
                started_at=EARLIER,
                package="rra004.package.v2",
                formula="rra004.formula.v1",
            ),
        ),
        bindings=_bindings("run-a", "run-b", "run-c"),
    )

    notice = _notice(_detail(records, _StubProvenance(), "run-c"))

    assert f'href="{SHELL_PREFIX}/en/{ORGANIZATION}/analyses/run-b"' in notice
    assert "run-a" not in notice and "run-x" not in notice
    # Same data, so the mapping did not change; the package and formula did.
    assert EN["notice_mapping"] not in notice
    assert EN["notice_package"] in notice and EN["notice_formula"] in notice


# --- Through the deployed pipeline ----------------------------------------------------------------


def test_a_single_run_carries_no_notice() -> None:
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)

    html = page(j, who, f"analyses/{run.run_id}")

    assert 'class="change-notice"' not in html


def test_two_runs_of_one_file_under_one_methodology_carry_no_notice() -> None:
    from tests.w104b_support import commercial_client, request_report, submit

    j = journey()
    who = member(j.w)
    completed_run(j, who)
    second, _session = commercial_client(j, who)
    submit(second)
    j.run_job(request_report(second))
    runs = j.w.store.analysis_runs_for_scope(who.owner_id)
    assert len(runs) == 2

    html = page(j, who, f"analyses/{runs[0].run_id}")

    assert 'class="change-notice"' not in html
    assert f'href="{detail_address(who, runs[1].run_id)}"' not in html
