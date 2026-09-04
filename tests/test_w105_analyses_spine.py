"""`W1-05` (second PR) -- the Analyses history spine (`RCA-005` `FR-117`, `FR-121`, `FR-122`).

**One list, newest first, and nothing that narrows it.** Blueprint §7.3 locks the spine as the
single history: no filter system, no Compare, no fixed result count. The rows are the scope's live
runs and its run tombstones, merged by the instant each started, newest first. A tombstone row
reads as a tombstone in both languages and offers no content action (`FR-122`; `KHEPRI-DEC-033`
§1: the row remains so history does not silently shorten).

**What a row states, and what it cannot yet.** `FR-117` names seven things. Five are here: when it
ran, which data it used (stated as when that data was submitted -- `DatasetVersion` and its
identifier never appear on screen, blueprint §7.2), its operational state, whether its report is
available, and its retention state. The other two are stated in this module's plan and not
rendered, because rendering either would be a claim the record cannot back:

- *Trust state* comes "through `RRA-012`'s components where a bundle state is shown". No bundle
  state is persisted for a live run -- `AnalysisRunRow` carries no section states, the delivery
  record carries `narrative_state` only, and the bundle is not retained. The one record that
  carries section codes is the run tombstone, and §7.3 makes a tombstone *minimal*. So no row shows
  a trust state, no second vocabulary is reached for (the `G3-04` plan's named risk), and the
  owner is told that showing one needs section states recorded at completion.
- *The next valid action* is rendered only where a route exists to take it. Analysis detail is
  `W1-06`'s and Run Again has a service (`W1-04`) but no route, so no row offers an action yet.
  `RCA-002` `FR-049` forbids a control with nothing behind it.

**No figure, as on Overview.** The visible text with `<time>` elements removed carries no digit:
no result count, no percentage, no total.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import unescape
from importlib.resources import files

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.organizations import Organization
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.contracts import (
    RUN_COMPLETED,
    RUN_FAILED,
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
from khepri.rca.workspace.tombstones import RunTombstone, RunTrace
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_copy import SHELL_COPY

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
EARLIER = datetime(2026, 9, 4, 9, 30, tzinfo=UTC)
EARLIEST = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)
DELETED_AT = datetime(2026, 9, 4, 18, 0, tzinfo=UTC)

ORGANIZATION = "org-acme"
SCOPE = "scope-acme"
DIGEST = "d" * 64


@dataclass
class _Context:
    account_id: str
    organization_id: str | None
    role: str | None = "owner"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


class _StubResolver:
    def __init__(self, context: _Context) -> None:
        self._context = context

    def for_request(self, token: str, *, organization_id: str | None, now: object) -> _Context:
        return self._context

    def require_owner(self, token: str, *, organization_id: str, now: object) -> _Context:
        return self._context


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


@dataclass
class _StubRecords:
    """A reader that returns what it was given and records which scope each read was for."""

    versions: tuple[DatasetVersion, ...] = ()
    runs: tuple[AnalysisRun, ...] = ()
    tombstones: tuple[RunTombstone, ...] = ()
    bindings: tuple[ArtifactBinding, ...] = ()
    asked: list[str] = field(default_factory=list)

    def dataset_versions_for_scope(self, owner_id: str) -> tuple[DatasetVersion, ...]:
        self.asked.append(owner_id)
        return self.versions

    def analysis_runs_for_scope(self, owner_id: str) -> tuple[AnalysisRun, ...]:
        self.asked.append(owner_id)
        return self.runs

    def tombstones_for_scope(self, owner_id: str) -> tuple[RunTombstone, ...]:
        self.asked.append(owner_id)
        return self.tombstones

    def artifact_bindings_for_scope(self, owner_id: str) -> tuple[ArtifactBinding, ...]:
        self.asked.append(owner_id)
        return self.bindings


def _version(version_id: str, *, created_at: datetime) -> DatasetVersion:
    return DatasetVersion._from_storage(
        version_id=version_id,
        owner_id=SCOPE,
        source=AdmittedSource(
            plaintext_digest=DIGEST,
            ciphertext_digest=DIGEST,
            size_bytes=4096,
            media_type="text/csv",
            manifest_digest=DIGEST,
            mapping_version="mapping-v-alpha",
            admission_outcome="admitted",
        ),
        lifecycle=VersionLifecycle(created_at=created_at, sealed_at=created_at),
    )


def _run(run_id: str, version_id: str, *, state: str, started_at: datetime) -> AnalysisRun:
    outcome = (
        RunOutcome(
            state=state,
            package_digest=DIGEST,
            package_version="package-v-alpha",
            formula_version="formula-v-alpha",
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


def _tombstone(run_id: str, version_id: str, *, started_at: datetime) -> RunTombstone:
    return RunTombstone._from_storage(
        subject=RunSubject(run_id=run_id, owner_id=SCOPE, version_id=version_id),
        trace=RunTrace(
            started_at=started_at,
            completed_at=started_at,
            package_digest=DIGEST,
            package_version="package-v-alpha",
            formula_version="formula-v-alpha",
            sections=dict.fromkeys(
                ("overview", "comparison", "concentration", "growth", "basket"), "answered"
            ),
        ),
        deleted_at=DELETED_AT,
    )


def _bindings(run_id: str, kinds=REQUIRED_ARTIFACT_KINDS) -> tuple[ArtifactBinding, ...]:
    return tuple(
        ArtifactBinding._from_storage(
            run_id=run_id,
            owner_id=SCOPE,
            artifact=PublishedArtifact(surface=kind, artifact_digest=DIGEST),
            published_at=NOW,
        )
        for kind in kinds
    )


def _shell(records: _StubRecords | None, *, context: _Context | None = None) -> TestClient:
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(context or _Context("acct-a", ORGANIZATION)),
            organizations=_StubOrganizations(),
            records=records,
            isolation=_StubIsolation() if records is not None else None,
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def _spine(records: _StubRecords, language: str = "en") -> str:
    return _shell(records).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/analyses").text


def _nav(html: str) -> str:
    start = html.index('class="frame-surfaces"')
    return html[start : html.index("</nav>", start)]


def _rows(html: str) -> list[str]:
    """Each row's markup, in document order, from its opening tag to the next row's."""
    return html.split('<li class="spine-item')[1:]


def _link(language: str, surface: str) -> str:
    return f'href="{SHELL_PREFIX}/{language}/{ORGANIZATION}/{surface}"'


def _history() -> _StubRecords:
    """Three live runs and one deleted one, over two data versions, as the store returns them:
    runs newest first, tombstones oldest deletion first."""
    return _StubRecords(
        versions=(
            _version("ver-b", created_at=EARLIER),
            _version("ver-a", created_at=EARLIEST),
        ),
        runs=(
            _run("run-d", "ver-b", state=RUN_STARTED, started_at=NOW),
            _run("run-c", "ver-b", state=RUN_FAILED, started_at=EARLIER),
            _run("run-a", "ver-a", state=RUN_COMPLETED, started_at=EARLIEST),
        ),
        tombstones=(
            _tombstone("run-b", "ver-a", started_at=datetime(2026, 9, 3, 20, 0, tzinfo=UTC)),
        ),
        bindings=_bindings("run-a"),
    )


# --- navigation ---------------------------------------------------------------------------------


class TestTheAnalysesLinkShipsWithItsSurface:
    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_four_destinations_in_fr121s_order(self, language: str) -> None:
        nav = _nav(_shell(_history()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/team").text)

        positions = [
            nav.index(_link(language, surface))
            for surface in ("overview", "data", "analyses", "team")
        ]
        assert positions == sorted(positions)
        assert SHELL_COPY[language]["analyses_title"] in nav

    def test_without_a_reader_there_is_no_analyses(self) -> None:
        shell = _shell(None)

        assert _link("en", "analyses") not in _nav(
            shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/team").text
        )
        assert shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/analyses").status_code == 404

    def test_the_current_surface_is_marked(self) -> None:
        nav = _nav(_spine(_history()))

        current = re.findall(r'<a href="([^"]+)"[^>]*aria-current="page"', nav)
        assert current == [f"{SHELL_PREFIX}/en/{ORGANIZATION}/analyses"]

    @pytest.mark.parametrize("language,alternate", [("en", "ar"), ("ar", "en")])
    def test_the_language_control_keeps_the_surface(self, language: str, alternate: str) -> None:
        html = _spine(_history(), language)

        assert f'href="{SHELL_PREFIX}/{alternate}/{ORGANIZATION}/analyses"' in html


# --- the spine ------------------------------------------------------------------------------------


class TestTheSpine:
    """`FR-117`, blueprint §7.3."""

    def test_every_run_and_every_tombstone_is_a_row_newest_first(self) -> None:
        rows = _rows(_spine(_history()))

        assert len(rows) == 4
        starts = [re.search(r'datetime="([^"]+)"', row).group(1) for row in rows]
        assert starts == sorted(starts, reverse=True)
        assert starts[0].startswith("2026-09-05")
        assert starts[-1].startswith("2026-09-03T08")

    def test_the_deleted_run_sits_where_it_started_not_where_it_was_deleted(self) -> None:
        """Merged by the instant each run started, so history reads in the order it happened;
        the deletion instant is stated on the row, not used to place it."""
        rows = _rows(_spine(_history()))

        tombstones = [i for i, row in enumerate(rows) if "spine-item--tombstone" in row]
        assert tombstones == [2]

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_a_live_row_states_when_which_data_state_report_and_retention(
        self, language: str
    ) -> None:
        copy = SHELL_COPY[language]
        rows = _rows(_spine(_history(), language))
        newest = rows[0]

        assert 'datetime="2026-09-05T12:00:00+00:00"' in newest
        assert copy["spine_data_submitted"] in newest
        assert 'datetime="2026-09-04T09:30:00+00:00"' in newest
        assert copy["run_state_started"] in newest
        assert copy["report_not_yet"] in newest
        assert copy["retention_kept"] in newest

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_report_availability_follows_the_bindings(self, language: str) -> None:
        """A completed run with every required artifact bound has a report; one without has
        none to offer. `FR-111` makes completion imply the full set, and the row says what the
        bindings say rather than what the state implies."""
        copy = SHELL_COPY[language]
        full = _rows(_spine(_history(), language))[-1]
        partial_records = _history()
        partial_records.bindings = _bindings("run-a", REQUIRED_ARTIFACT_KINDS[:1])
        partial = _rows(_spine(partial_records, language))[-1]

        assert copy["report_available"] in full
        assert copy["report_unavailable"] in partial
        assert copy["report_available"] not in partial

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_a_failed_run_has_no_report(self, language: str) -> None:
        copy = SHELL_COPY[language]
        failed = _rows(_spine(_history(), language))[1]

        assert copy["run_state_failed"] in failed
        assert copy["report_unavailable"] in failed
        assert copy["report_available"] not in failed

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_a_tombstone_reads_as_a_tombstone_with_no_content_action(self, language: str) -> None:
        """`FR-122`, `KHEPRI-DEC-033` §1. Deleted, when it started, when it was deleted -- and no
        state word, no report word, no link, no form, nothing from its sections."""
        copy = SHELL_COPY[language]
        row = _rows(_spine(_history(), language))[2]

        assert "spine-item--tombstone" in row
        assert copy["tombstone_deleted"] in row
        assert 'datetime="2026-09-04T18:00:00+00:00"' in row
        assert 'datetime="2026-09-03T20:00:00+00:00"' in row
        for state in ("run_state_started", "run_state_completed", "run_state_failed"):
            assert copy[state] not in row
        for word in ("report_available", "report_not_yet", "report_unavailable"):
            assert copy[word] not in row
        assert "<a " not in row and "<form" not in row and "<button" not in row
        assert "answered" not in row

    def test_no_row_offers_an_action_this_slice_cannot_honour(self) -> None:
        """`FR-049`: Analysis detail is `W1-06`'s and Run Again has no route, so no row carries a
        link or a form. When those ship, this assertion is replaced, not relaxed."""
        html = _spine(_history())
        spine = html[html.index('class="spine-list"') :]

        assert "<a " not in spine and "<form" not in spine and "<button" not in spine

    def test_no_filter_no_compare_no_count(self) -> None:
        """Blueprint §7.3's three prohibitions, and `FR-120`'s figure rule carried over."""
        html = _spine(_history())
        body = html.split("<body", 1)[1]
        text = unescape(
            re.sub(r"<[^>]+>", "", re.sub(r"<time\b[^>]*>.*?</time>", "", body, flags=re.DOTALL))
        )

        assert "<input" not in body and "<select" not in body
        assert 'method="get"' not in body
        assert re.search(r"\d", text) is None, text
        for language in ("en", "ar"):
            assert "compare" not in text.lower() and "قارن" not in text

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_an_empty_history_says_so(self, language: str) -> None:
        html = _spine(_StubRecords(), language)

        assert SHELL_COPY[language]["analyses_empty"] in html
        assert "spine-item" not in html

    def test_no_internal_identifier_reaches_the_row(self) -> None:
        html = _spine(_history())

        for token in (
            DIGEST,
            "package-v-alpha",
            "formula-v-alpha",
            "mapping-v-alpha",
            "ver-a",
            "run-a",
        ):
            assert token not in html, token
        assert "dataset" not in html.lower()

    def test_a_tombstone_shows_no_trust_state(self) -> None:
        """The plan's named risk is a second trust vocabulary. The tombstone is the one record that
        carries section codes and it is rendered minimal (§7.3), so no badge, no summary, and no
        `RRA-012` component appears on this surface at all."""
        html = _spine(_history())

        assert "data-component=" not in html
        for word in ("Answered", "Refused", "تمت الإجابة", "مرفوض"):
            assert word not in html


# --- scope -------------------------------------------------------------------------------------------


def test_every_read_is_for_the_sessions_scope() -> None:
    records = _StubRecords()

    _shell(records).get(f"{SHELL_PREFIX}/en/org-other/analyses")

    assert len(records.asked) == 4, records.asked
    assert set(records.asked) == {SCOPE}


def test_the_template_is_in_the_scanned_set() -> None:
    directory = files("khepri.runtime").joinpath("shell_templates")
    assert "analyses.html.j2" in {entry.name for entry in directory.iterdir()}
