"""`W1-05` (second PR) -- the staged Analyses history spine (`RCA-005` `FR-117`, `FR-122`).

**One list, newest first, and nothing that narrows it.** Blueprint §7.3 locks the spine as the
single history: no filter system, no Compare, no fixed result count. The rows are the scope's live
runs and its run tombstones, merged by the instant each started, newest first. A tombstone row
reads as a tombstone in both languages and offers no content action (`FR-122`; `KHEPRI-DEC-033`
§1: the row remains so history does not silently shorten).

**What a staged row states, and why it is not exposed.** `FR-117` names seven things. Five can be
shaped faithfully: when it ran, which exact Data row it used, its operational state, whether its
report is available, and its retention state. The other two cannot yet be backed:

- *Trust state* comes "through `RRA-012`'s components where a bundle state is shown". No bundle
  state is persisted for a live run -- `AnalysisRunRow` carries no section states, the delivery
  record carries `narrative_state` only, and the bundle is not retained. The one record that
  carries section codes is the run tombstone, and §7.3 makes a tombstone *minimal*. So no row shows
  a trust state, no second vocabulary is reached for (the `G3-04` plan's named risk), and the
  adding one needs section states recorded at completion.
- *The next valid action* is rendered only where a route exists to take it. Analysis detail is
  `W1-06`'s and Run Again has a service (`W1-04`) but no route, so no row offers an action yet.
  `RCA-002` `FR-049` forbids a control with nothing behind it.

Therefore the navigation destination and guessed address are withheld. The tests exercise the
internal renderer as a hardened staging boundary, including atomic history reads, exact Data-row
references, tombstone precedence, and refusal of incomplete completed records.

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
from khepri.rca.workspace.persistence import WorkspaceHistory
from khepri.rca.workspace.tombstones import (
    RunTombstone,
    RunTrace,
    VersionSubject,
    VersionTombstone,
)
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.runtime.shell_api import (
    SHELL_PREFIX,
    ShellServices,
    _analyses_response,
    add_shell_routes,
    shell_environment,
)
from khepri.runtime.shell_copy import SHELL_COPY
from khepri.runtime.shell_workspace import UnrenderableRecord, spine_rows

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
EARLIER = datetime(2026, 9, 4, 9, 30, tzinfo=UTC)
EARLIEST = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)
DELETED_AT = datetime(2026, 9, 4, 18, 0, tzinfo=UTC)
#: When the older data version was submitted: its own instant, distinct from every run's, so a
#: row that showed the wrong version's submission would be caught.
OLDER_DATA_AT = datetime(2026, 9, 2, 7, 0, tzinfo=UTC)

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
    tombstones: tuple[RunTombstone | VersionTombstone, ...] = ()
    bindings: tuple[ArtifactBinding, ...] = ()
    asked: list[str] = field(default_factory=list)

    def history_for_scope(self, owner_id: str) -> WorkspaceHistory:
        self.asked.append(owner_id)
        return WorkspaceHistory(
            versions=self.versions,
            runs=self.runs,
            bindings=self.bindings,
            tombstones=self.tombstones,
        )


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


def _version_tombstone(version_id: str, *, created_at: datetime) -> VersionTombstone:
    return VersionTombstone._from_storage(
        subject=VersionSubject(version_id=version_id, owner_id=SCOPE),
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


def _services(
    records: _StubRecords | None, *, context: _Context | None = None
) -> ShellServices:
    return ShellServices(
        resolver=_StubResolver(context or _Context("acct-a", ORGANIZATION)),
        organizations=_StubOrganizations(),
        records=records,
        isolation=_StubIsolation() if records is not None else None,
    )


def _shell(records: _StubRecords | None, *, context: _Context | None = None) -> TestClient:
    app = FastAPI()
    add_shell_routes(app, services=_services(records, context=context), clock=lambda: NOW)
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def _spine(records: _StubRecords, language: str = "en") -> str:
    response = _analyses_response(
        _services(records),
        shell_environment(),
        language=language,
        context=_Context("acct-a", ORGANIZATION),
    )
    return response.body.decode()


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
            _version("ver-a", created_at=OLDER_DATA_AT),
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


class TestTheAnalysesSurfaceWaitsForItsRequirements:
    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_shipped_destinations_exclude_analyses(self, language: str) -> None:
        """`FR-117` requires trust state and a next valid action. Neither can be read or followed
        yet, so `FR-049` withholds it instead of shipping a knowingly partial surface.
        """
        nav = _nav(_shell(_history()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/team").text)

        positions = [
            nav.index(_link(language, surface)) for surface in ("overview", "data", "team")
        ]
        assert positions == sorted(positions)
        assert _link(language, "analyses") not in nav

    @pytest.mark.parametrize("records", [_history(), None])
    def test_the_analyses_address_is_withheld(self, records: _StubRecords | None) -> None:
        shell = _shell(records)

        assert _link("en", "analyses") not in _nav(
            shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/team").text
        )
        assert shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/analyses").status_code == 404


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
        assert f'href="{SHELL_PREFIX}/{language}/{ORGANIZATION}/data#data-ver-b"' in newest
        assert copy["run_state_started"] in newest
        assert copy["report_not_yet"] in newest
        assert copy["retention_kept"] in newest

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_report_availability_follows_the_bindings(self, language: str) -> None:
        """A completed run with every required artifact bound has a report."""
        copy = SHELL_COPY[language]
        full = _rows(_spine(_history(), language))[-1]

        assert copy["report_available"] in full

    def test_an_incomplete_completed_run_is_unrenderable(self) -> None:
        """`FR-111`: a persisted completed run missing a required binding is corrupt, not a
        completed row whose report happens to be unavailable (review on `#374`)."""
        partial_records = _history()
        partial_records.bindings = _bindings("run-a", REQUIRED_ARTIFACT_KINDS[:1])

        with pytest.raises(UnrenderableRecord):
            spine_rows(
                partial_records.runs,
                partial_records.tombstones,
                partial_records.versions,
                partial_records.bindings,
            )

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

    def test_each_row_states_its_own_versions_submission(self) -> None:
        """ "Which data it used" is the submission instant of *that* run's version, matched by
        `version_id` -- not the first version in the scope."""
        rows = _rows(_spine(_history()))
        newest, oldest = rows[0], rows[-1]

        assert 'datetime="2026-09-04T09:30:00+00:00"' in newest
        assert 'datetime="2026-09-02T07:00:00+00:00"' not in newest
        assert 'datetime="2026-09-02T07:00:00+00:00"' in oldest
        assert 'datetime="2026-09-04T09:30:00+00:00"' not in oldest

    def test_a_tombstone_row_carries_no_state_and_no_report_key(self) -> None:
        """Asserted on the row model, not only on the markup: the template happens not to render a
        tombstone's state, and a model that carried one would be one edit from showing it."""
        records = _history()

        rows = spine_rows(records.runs, records.tombstones, records.versions, records.bindings)
        tombstones = [row for row in rows if row.deleted is not None]

        assert len(tombstones) == 1
        assert tombstones[0].state_key is None and tombstones[0].report_key is None
        assert tombstones[0].retention_key == "retention_deleted"

    def test_no_row_offers_an_action_this_slice_cannot_honour(self) -> None:
        """`FR-049`: Analysis detail is `W1-06`'s and Run Again has no route, so the only link on a
        row is the reference to its data entry on the Data surface, which exists. When detail
        ships, this assertion is replaced, not relaxed."""
        html = _spine(_history())
        spine = html[html.index('class="spine-list"') :]

        assert "<form" not in spine and "<button" not in spine
        for href in re.findall(r'<a [^>]*href="([^"]+)"', spine):
            assert href.startswith(f"{SHELL_PREFIX}/en/{ORGANIZATION}/data#data-"), href

    def test_two_entries_submitted_at_the_same_instant_are_two_references(self) -> None:
        """`FR-117`: a row identifies *which* data entry it used. The schema permits two versions
        with one `created_at`, so the reference is the entry's anchor on the Data surface -- the
        row's `id` there -- and not its timestamp (review on `#374`)."""
        records = _StubRecords(
            versions=(
                _version("ver-twin-b", created_at=EARLIER),
                _version("ver-twin-a", created_at=EARLIER),
            ),
            runs=(
                _run("run-b", "ver-twin-b", state=RUN_STARTED, started_at=NOW),
                _run("run-a", "ver-twin-a", state=RUN_STARTED, started_at=EARLIER),
            ),
        )

        spine = _spine(records)
        data = _shell(records).get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/data").text
        rows = _rows(spine)

        assert f'href="{SHELL_PREFIX}/en/{ORGANIZATION}/data#data-ver-twin-b"' in rows[0]
        assert f'href="{SHELL_PREFIX}/en/{ORGANIZATION}/data#data-ver-twin-a"' in rows[1]
        assert 'id="data-ver-twin-b"' in data and 'id="data-ver-twin-a"' in data

    def test_a_run_whose_data_was_deleted_says_so(self) -> None:
        """The version is gone from the live listing; its tombstone still states when it was
        submitted, and the row says the data was deleted with nothing to follow."""
        records = _StubRecords(
            versions=(),
            runs=(_run("run-a", "ver-gone", state=RUN_COMPLETED, started_at=NOW),),
            tombstones=(_version_tombstone("ver-gone", created_at=EARLIEST),),
            bindings=_bindings("run-a"),
        )

        row = _rows(_spine(records))[0]

        assert SHELL_COPY["en"]["spine_data_deleted"] in row
        assert 'datetime="2026-09-03T08:00:00+00:00"' in row
        assert "<a " not in row

    def test_a_run_both_live_and_deleted_reads_as_deleted(self) -> None:
        """`FR-127`: a deletion committed between the reads of one history shows the same run live
        and tombstoned. The deletion is the later fact; one row, a tombstone (review on `#374`)."""
        records = _history()
        records.tombstones = records.tombstones + (_tombstone("run-d", "ver-b", started_at=NOW),)

        rows = _rows(_spine(records))

        assert len(rows) == 4
        assert "spine-item--tombstone" in rows[0]
        assert SHELL_COPY["en"]["run_state_started"] not in rows[0]

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
        assert "compare" not in text.lower() and "قارن" not in text

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_an_empty_history_says_so(self, language: str) -> None:
        html = _spine(_StubRecords(), language)

        assert SHELL_COPY[language]["analyses_empty"] in html
        assert "spine-item" not in html

    def test_no_internal_identifier_reaches_the_rows_text(self) -> None:
        """§7.2: digests, versions and identifiers are not what a row *says*. The opaque version
        identifier travels inside the data reference's `href`, the way organization identifiers do
        across the shell, and nowhere in the text."""
        html = _spine(_history())
        text = re.sub(r"<[^>]+>", "", html)

        for token in (
            DIGEST,
            "package-v-alpha",
            "formula-v-alpha",
            "mapping-v-alpha",
            "ver-a",
            "run-a",
        ):
            assert token not in text, token
        assert "run-a" not in html and DIGEST not in html
        assert "dataset" not in html.lower()

    def test_a_tombstone_shows_no_trust_state(self) -> None:
        """The plan's named risk is a second trust vocabulary. The tombstone is the one record that
        carries section codes and it is rendered minimal (§7.3), so no badge, no summary, and no
        `RRA-012` component appears on this surface at all."""
        html = _spine(_history())

        assert "data-component=" not in html
        for word in ("Answered", "Refused", "تمت الإجابة", "مرفوض"):
            assert word not in html


# --- scope --------------------------------------------------------------------------------


def test_every_read_is_for_the_sessions_scope() -> None:
    records = _StubRecords()

    _spine(records)

    assert records.asked == [SCOPE], "one read, in one transaction, for the session's scope"


def test_the_template_is_in_the_scanned_set() -> None:
    directory = files("khepri.runtime").joinpath("shell_templates")
    assert "analyses.html.j2" in {entry.name for entry in directory.iterdir()}
