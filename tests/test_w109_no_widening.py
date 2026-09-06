"""The guard `RCA-005` Verification names: `KHEPRI-DEC-034` must not be widened by implementation.

> "A test that `FR-128`/`FR-129` write **no** access record, counter or telemetry event, and that a
> pin emits no audit event -- the guard against `KHEPRI-DEC-034` being widened by implementation."

This module exists because the decision it guards is narrow *by choice*. §2 keeps
`KHEPRI-DEC-015` §3 unamended, leaves `W1-11` and `R8-08` excluded, and refuses counting, ranking
and frequency. Each refusal is one line of prose and one plausible feature away from being lost --
"most used", "opened 12 times", "trending" are all things a reasonable person would build next --
so each gets an assertion here rather than a reviewer's attention.

Every assertion is checked against a mutant in the slice's ledger: a guard that survives its own
mutant is not tested, and mutation testing cannot find a guard that was never written.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy import inspect

from khepri.rca.persistence import Base
from khepri.rca.workspace.audit import AUDIT_ACTIONS
from khepri.rca.workspace.persistence import WorkspacePinRow
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w107_support import NOW, sealed_version

#: Words that would each mean an access record had been introduced, matched against a column
#: name's underscore-separated *parts*.
#:
#: Words rather than exact column names, because the widening arrives under whatever name its
#: author chose -- `opened_count`, `view_counter`, `use_frequency` are one defect. Parts rather
#: than substrings, because `actor_account_id` contains "count" and is an opaque identifier: a
#: substring scan flags it, and a guard that cries wolf gets its fragment list trimmed until it
#: stops catching the real thing.
COUNTER_WORDS = frozenset(
    {
        "count",
        "counter",
        "counts",
        "frequency",
        "opened",
        "opens",
        "viewed",
        "views",
        "accessed",
        "accesses",
        "rank",
        "ranking",
        "weight",
    }
)

#: The one counting column the workspace legitimately holds, named so the scan above can be
#: blanket rather than clever.
#:
#: **A data count is not a behaviour count**, and the distinction is the whole of what
#: `KHEPRI-DEC-034` §2 refuses. `rca_workspace_run_provenance.row_count` says how many source rows
#: a run covered -- governed analytical provenance under `FR-116`, sitting beside `covered_start`
#: and `covered_end`. It measures the *customer's data*. §2 refuses counting the *customer*: how
#: often they opened something, how many times a report was viewed.
#:
#: Written as an exact `(table, column)` pair rather than dropping "count" from the fragments, so
#: a second counting column -- `rca_workspace_pins.open_count`, say -- still fails. The narrowest
#: exemption that admits the real one.
ADMITTED_COUNTS = frozenset({("rca_workspace_run_provenance", "row_count")})


def _workspace_tables() -> dict:
    """Every workspace table, derived from the metadata rather than hand-listed.

    A scan that names its own scope reproduces the drift it was written to catch: a table added
    later would go unscanned while this still reported a pass. The emptiness assertion is the
    other half -- a scan that silently finds nothing reports as a passed one.
    """
    tables = {
        name: table
        for name, table in Base.metadata.tables.items()
        if name.startswith("rca_workspace_")
    }
    assert tables, "the metadata yielded no workspace tables, so this guard checks nothing"
    return tables


class TestNoAuditEventIsEmitted:
    def test_pinning_and_unpinning_emit_no_audit_event(self) -> None:
        """`FR-128`: a pin "is not a governed workspace action: it emits **no** `FR-125` audit
        event and adds no member to `AUDIT_ACTIONS`."

        A pin is not a governed action because it changes nothing about the content -- it records
        what one person wants to find again. An audit event for it would put a behavioural trace
        into the record `KHEPRI-DEC-015` §7 reserves for security and audit, which is the
        conversion `RCA-005` forbids from the other direction.
        """
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        before = len(j.w.audit.events_for_scope(who.owner_id))

        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)
        j.w.store.unpin(version.version_id, owner_id=who.owner_id)

        assert len(j.w.audit.events_for_scope(who.owner_id)) == before

    def test_the_audit_vocabulary_gained_no_member(self) -> None:
        """A vocabulary is pinned in three places -- this tuple, the closed-set test in
        `test_w104_audit_events.py`, and the migration's CHECK literal. Adding a pin action would
        have to move all three.

        **Exact extent, not a count and not a pair of absences.** `len(...) == 8` breaks on a
        legitimate unrelated widening while proving nothing about *which* members are present, and
        `"pin_added" not in ...` cannot see a member added under any other name. `RCA_TABLES`
        drifted three times under assertions that could only ever weaken.
        """
        assert AUDIT_ACTIONS == (
            "version_created",
            "run_started",
            "run_completed",
            "run_failed",
            "profile_remembered",
            "profile_reused",
            "version_deleted",
            "retention_swept",
        )


class TestNoCounterExists:
    def test_the_pin_row_carries_no_count_or_access_field(self) -> None:
        """`KHEPRI-DEC-034` §2 refuses "counting, ranking, or frequency" by name.

        The field list is asserted for *equality* in `test_w109_pins.py`, which is the stronger
        check; this states the refusal in the vocabulary the decision uses, so a reader grepping
        for "count" finds it here.
        """
        columns = {column.name for column in inspect(WorkspacePinRow).columns}

        for column in columns:
            assert not (set(column.split("_")) & COUNTER_WORDS), column

    def test_no_workspace_table_gained_a_counter(self) -> None:
        """Scoped across every workspace table, not the pin table alone.

        A counter added to satisfy "most used" would more likely land on the version or run row
        than on a table of its own -- and a guard that scanned only the table this slice added
        would be looking exactly where the defect is least likely to appear.

        `ADMITTED_COUNTS` exempts the one data count the workspace holds, by exact name. It is
        also asserted non-empty and fully matched below, so an exemption that stops describing a
        real column fails rather than quietly widening the scan's blind spot.
        """
        for name, table in _workspace_tables().items():
            for column in table.columns:
                if (name, column.name) in ADMITTED_COUNTS:
                    continue
                offending = set(column.name.split("_")) & COUNTER_WORDS
                assert not offending, f"{name}.{column.name}"

    def test_every_admitted_count_still_exists(self) -> None:
        """The exemption list describes real columns, and no more than it needs to.

        An exemption for a column that has since been renamed or removed is a hole in the scan
        that nothing else would report: the guard would keep passing while the name it excused no
        longer exists, and a *new* column arriving under that name would be excused for free.
        """
        assert ADMITTED_COUNTS, "an empty exemption set means the scan below checks nothing"

        tables = _workspace_tables()
        for table_name, column_name in ADMITTED_COUNTS:
            assert table_name in tables, table_name
            assert column_name in tables[table_name].columns, f"{table_name}.{column_name}"


class TestTheExclusionsStand:
    def test_both_governing_decisions_are_active(self) -> None:
        """`KHEPRI-DEC-034` §2: "`KHEPRI-DEC-015` §3 is **not amended** by this decision. Product
        analytics remains an unauthorized purpose, `W1-11` remains excluded, and `R8-08` remains
        excluded."

        **This asserts the registry state, not the prose.** A first draft checked that the phrase
        "product analytics" appeared in `KHEPRI-DEC-015` -- which passes even if §3 were rewritten
        to *permit* product analytics, as long as the words survived. A test that cannot fail for
        the reason it names is worse than no test, because it reports as evidence.

        Constitution III makes the registry authoritative, and `AGENTS.md` says to answer "is X
        approved?" from the registry `state`, never from prose or green CI.
        """
        # Anchored to the repository root rather than the process working directory, following
        # `test_governance_validator.py` and `test_portable_storage_boundary.py`: pytest may run
        # from elsewhere, and a CWD-relative read then raises `FileNotFoundError` instead of
        # answering the question. Review on `#390`.
        root = Path(__file__).resolve().parents[1]
        registry = yaml.safe_load(
            (root / "governance" / "registry.yaml").read_text(encoding="utf-8")
        )
        states = {
            entry["id"]: entry["state"]
            for entry in registry["artifacts"]
            if entry.get("type") == "decision"
        }

        assert states["KHEPRI-DEC-015"] == "active"
        assert states["KHEPRI-DEC-034"] == "active"

    def test_this_slice_added_no_telemetry_table(self) -> None:
        """The workspace tables are a closed set this slice extended by exactly one.

        Equality rather than membership: `W1-09` adds `rca_workspace_pins` and nothing else, and
        an "activity" or "events" table appearing here would be the telemetry `FR-129` refuses --
        under whatever name it arrived.
        """
        assert set(_workspace_tables()) == {
            "rca_workspace_dataset_versions",
            "rca_workspace_analysis_runs",
            "rca_workspace_artifact_bindings",
            "rca_workspace_source_profiles",
            "rca_workspace_tombstones",
            "rca_workspace_audit_events",
            "rca_workspace_run_reports",
            "rca_workspace_run_provenance",
            "rca_workspace_revocations",
            "rca_workspace_pins",
        }
