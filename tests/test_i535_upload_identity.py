"""#535: a dataset version keeps its upload's identity across a re-seal (`RCA-005` `FR-255`+).

`RRA-002`'s encryption is randomised, so re-sealing an upload changes
`rra_uploads.ciphertext_sha256_hex`, and `FR-112` keeps a version's recorded digest from following
it. The three joins that matched on that digest -- the raw-upload purge, the version-deletion
session lookup and the version-creation retry -- would each miss a re-sealed upload. `FR-255` gives
the version the upload's primary key, `upload_id`, and `FR-259`-`FR-261` re-key the joins onto it.

**The re-seal here is the row change `FR-263`(a) prescribes**: the same `rra_uploads` row, the same
`upload_id` and `object_key`, a new ciphertext digest and envelope version, the object rewritten at
its key. The journey's object store is the in-memory double, so the bytes are not a real `v2`
envelope; the property under test is the join, which reads the row, not the bytes. Each case first
asserts that the pre-amendment digest join finds nothing on its own fixture, so a fixture whose
digest did not change cannot pass it.

SQLite here; the same cases, with the foreign key that clears `upload_id`, run on PostgreSQL in
`test_i535_upload_identity_postgres.py`. **Not a `test_rra*` file** (`RCA-001` `FR-037`).
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

import khepri
from khepri.rca.workspace.contracts import AdmittedSource, DatasetVersion, VersionKeys
from khepri.rca.workspace.persistence import (
    COMPLETION_COLUMNS,
    MUTABLE_COLUMNS,
    VERSION_TOMBSTONE_COLUMNS,
    DatasetVersionRow,
    SqlWorkspaceRecordStore,
)
from khepri.rca.workspace.store import VersionAlreadyRecorded
from khepri.rra.persistence import UploadRow
from tests.rca_lifecycle_support import factory_fixture  # noqa: F401 -- the `factory` fixture
from tests.test_w102_workspace_persistence import SOURCE, _scope
from tests.w104_support import NOW as ADMITTED_AT
from tests.w104_support import admitted_session, member
from tests.w104b_support import Journey, journey

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
UPLOAD = "upl_first"
OTHER_UPLOAD = "upl_second"


def _created(scope: str, upload_id: str = UPLOAD, source: AdmittedSource = SOURCE):
    return DatasetVersion.create(owner_id=scope, upload_id=upload_id, source=source, now=NOW)


# --- FR-255: the identity, and the door that writes it -----------------------------------------


def test_a_created_version_records_the_upload_it_was_admitted_from() -> None:
    version = _created("own_a")

    assert version.upload_id == UPLOAD


@pytest.mark.parametrize("absent", [None, ""])
def test_create_refuses_an_absent_or_empty_upload_identity(absent: str | None) -> None:
    with pytest.raises(ValueError) as refused:
        DatasetVersion.create(owner_id="own_a", upload_id=absent, source=SOURCE, now=NOW)

    assert "upl_" not in str(refused.value), "the refusal names the constraint, not a value"


def test_create_requires_the_upload_identity_as_a_keyword() -> None:
    with pytest.raises(TypeError):
        DatasetVersion.create(owner_id="own_a", source=SOURCE, now=NOW)  # type: ignore[call-arg]


def test_the_identity_is_not_on_the_admitted_source() -> None:
    """`FR-255`: the tombstone projections rebuild `AdmittedSource`, and must never carry it."""
    assert "upload_id" not in {field.name for field in fields(AdmittedSource)}


def test_the_version_subject_carries_identity_and_nothing_admission_decided() -> None:
    assert {field.name for field in fields(VersionKeys)} == {
        "version_id",
        "owner_id",
        "upload_id",
    }


# --- FR-256 / FR-257: written once, uniqueness on the identity ---------------------------------


def test_the_identity_round_trips_through_the_store(factory: sessionmaker) -> None:
    store = SqlWorkspaceRecordStore(factory)
    scope = _scope(factory)
    version = store.add_dataset_version(_created(scope))

    stored = store.get_dataset_version(version.version_id, scope)

    assert stored is not None
    assert stored.upload_id == UPLOAD


def test_a_second_version_for_one_upload_is_already_recorded(factory: sessionmaker) -> None:
    store = SqlWorkspaceRecordStore(factory)
    scope = _scope(factory)
    store.add_dataset_version(_created(scope))
    other_bytes = replace(SOURCE, ciphertext_digest="sha256:" + "f" * 64)

    with pytest.raises(VersionAlreadyRecorded):
        store.add_dataset_version(_created(scope, source=other_bytes))


def test_the_ciphertext_digest_no_longer_arbitrates(factory: sessionmaker) -> None:
    """`FR-257` drops the digest index: two uploads may record one observed digest."""
    store = SqlWorkspaceRecordStore(factory)
    scope = _scope(factory)
    store.add_dataset_version(_created(scope))

    store.add_dataset_version(_created(scope, upload_id=OTHER_UPLOAD))

    assert len(store.dataset_versions_for_scope(scope)) == 2


def test_an_orm_update_of_the_identity_is_refused(factory: sessionmaker) -> None:
    store = SqlWorkspaceRecordStore(factory)
    scope = _scope(factory)
    version = store.add_dataset_version(_created(scope))

    with factory() as database:
        row = database.get(DatasetVersionRow, version.version_id)
        row.upload_id = OTHER_UPLOAD
        with pytest.raises(ValueError):
            database.flush()


def test_the_mutable_and_completion_sets_are_unchanged() -> None:
    assert frozenset({"retention_state", "retention_changed_at", "sealed_at"}) == MUTABLE_COLUMNS
    assert "upload_id" not in COMPLETION_COLUMNS


def test_the_retry_lookup_refuses_an_absent_identity(factory: sessionmaker) -> None:
    """`IS NULL` would hand back a stranger's version whose upload is gone."""
    store = SqlWorkspaceRecordStore(factory)

    with pytest.raises(ValueError):
        store.dataset_version_for_upload("own_a", None)  # type: ignore[arg-type]


def test_the_version_tombstone_allowlist_is_unchanged() -> None:
    assert "upload_id" not in VERSION_TOMBSTONE_COLUMNS
    assert VERSION_TOMBSTONE_COLUMNS == (
        "version_id",
        "created_at",
        "sealed_at",
        "upload_plaintext_digest",
        "upload_ciphertext_digest",
        "upload_size_bytes",
        "upload_media_type",
        "manifest_digest",
        "mapping_version",
        "admission_outcome",
    )


# --- FR-259-FR-261 across a re-seal, through production verbs ----------------------------------


def reseal(j: Journey, owner_id: str) -> UploadRow:
    """Rewrite the scope's one upload in place, as `FR-263`(a) requires, and return it as was."""
    with j.w.factory() as database:
        (upload,) = database.scalars(select(UploadRow).where(UploadRow.owner_id == owner_id))
    rewritten = b"resealed:" + j.w.objects.objects[upload.object_key]
    j.w.objects.objects[upload.object_key] = rewritten
    with j.w.factory.begin() as database:
        database.execute(
            update(UploadRow)
            .where(UploadRow.upload_id == upload.upload_id)
            .values(ciphertext_sha256_hex=hashlib.sha256(rewritten).hexdigest(), envelope_version=2)
        )
    return upload


def assert_the_old_join_misses(j: Journey, version: DatasetVersion) -> None:
    """The fixture changed the digest: the pre-amendment join has nothing to find."""
    with j.w.factory() as database:
        found = database.scalar(
            select(UploadRow.upload_id).where(
                UploadRow.owner_id == version.owner_id,
                UploadRow.ciphertext_sha256_hex == version.upload_ciphertext_digest,
            )
        )
    assert found is None, "the fixture did not re-seal: the digest join still matches"


def sealed_and_resealed(j: Journey) -> tuple[Any, DatasetVersion, UploadRow]:
    from tests.w107_support import sealed_version

    who = member(j.w)
    version, _run = sealed_version(j, who, with_run=True)
    upload = reseal(j, who.owner_id)
    assert_the_old_join_misses(j, version)
    return who, version, upload


def check_the_purge_finds_a_resealed_upload(j: Journey) -> tuple[DatasetVersion, UploadRow]:
    from khepri.runtime.workspace_retention import RawUploadRetentionSweeper
    from tests.w107_support import uploads_for

    who, version, upload = sealed_and_resealed(j)
    assert version.sealed_at is not None

    swept = RawUploadRetentionSweeper(
        factory=j.w.factory, objects=j.w.objects, audit=j.w.audit
    ).sweep(now=version.sealed_at + timedelta(days=7))

    assert swept.purged_uploads == 1
    assert uploads_for(j, who.owner_id) == ()
    assert upload.object_key not in j.w.objects.objects
    return version, upload


def check_deletion_finds_the_session_of_a_resealed_upload(j: Journey) -> None:
    """Before any purge, with no run, so only the upload path can name the session."""
    from tests.w106_support import submitted
    from tests.w107_support import deletion_jobs_for, deletion_service

    who = member(j.w)
    submitted(j, who)
    (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
    reseal(j, who.owner_id)
    assert_the_old_join_misses(j, version)

    deletion_service(j).delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )

    assert len(deletion_jobs_for(j, who.owner_id)) == 1


def check_creation_stays_idempotent_across_a_reseal(j: Journey) -> None:
    from tests.w106_support import submitted

    who = member(j.w)
    _client, session_id = submitted(j, who)
    (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
    reseal(j, who.owner_id)
    assert_the_old_join_misses(j, version)

    again = j.w.services.create_dataset_version(who.caller, session_id=session_id, now=NOW)

    assert again.version_id == version.version_id
    assert j.w.store.dataset_versions_for_scope(who.owner_id) == (version,)
    assert j.w.audit.events_for_scope(who.owner_id)[-1].outcome == "already_recorded"


def test_the_purge_finds_a_resealed_upload() -> None:
    check_the_purge_finds_a_resealed_upload(journey())


def test_deletion_finds_the_session_of_a_resealed_upload() -> None:
    check_deletion_finds_the_session_of_a_resealed_upload(journey())


def test_creation_stays_idempotent_across_a_reseal() -> None:
    check_creation_stays_idempotent_across_a_reseal(journey())


def test_a_version_records_its_sessions_upload_and_no_event_carries_it() -> None:
    """`FR-255`'s boundary: the version row holds the identity, the audit trail does not."""
    j = journey()
    who = member(j.w)
    session_id = admitted_session(j.w, who.owner_id)
    with j.w.factory() as database:
        upload_id = database.scalar(
            select(UploadRow.upload_id).where(UploadRow.session_id == session_id)
        )

    version = j.w.services.create_dataset_version(
        who.caller, session_id=session_id, now=ADMITTED_AT
    )

    assert version.upload_id == upload_id
    for event in j.w.audit.events_for_scope(who.owner_id):
        for field in fields(event):
            assert upload_id not in str(getattr(event, field.name)), field.name


# --- FR-258: no query keys on the ciphertext digest ---------------------------------------------

PACKAGE = Path(khepri.__file__).resolve().parent
DIGEST = "upload_ciphertext_digest"
PREDICATES = {"where", "filter", "filter_by", "having", "join", "outerjoin", "on"}
SQL_CALLS = {"text", "execute", "exec_driver_sql"}
#: `FR-258`'s named exceptions, besides `migrations/` (outside the package): the row-to-record
#: projections, and `FR-262`'s repair.
EXEMPT = {
    PACKAGE / "rca" / "workspace" / "store.py": {"_version_from_row"},
    PACKAGE / "rca" / "workspace" / "tombstone_rows.py": None,
    PACKAGE / "runtime" / "upload_identity_repair.py": None,
}
SQL_PREDICATE_WORDS = (" where ", " on ", " join ")


def _is_the_column(node: ast.AST) -> bool:
    """`R.upload_ciphertext_digest`, or the name as a string: `getattr(R, ...)`, `R.c[...]`."""
    if isinstance(node, ast.Attribute):
        return node.attr == DIGEST
    return isinstance(node, ast.Constant) and node.value == DIGEST


def _names_the_digest(node: ast.AST) -> bool:
    return any(_is_the_column(inner) for inner in ast.walk(node))


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return call.func.id if isinstance(call.func, ast.Name) else None


def _keys_a_predicate(call: ast.Call) -> bool:
    """`where(...)`, `join(..., onclause=...)`, `filter_by(upload_ciphertext_digest=...)`."""
    if _call_name(call) not in PREDICATES:
        return False
    keywords = call.keywords
    return any(_names_the_digest(arg) for arg in call.args) or any(
        keyword.arg == DIGEST or _names_the_digest(keyword.value) for keyword in keywords
    )


def _is_sql_keyed_on_it(call: ast.Call) -> bool:
    """`text("... WHERE upload_ciphertext_digest = :d")`, or the same passed to `execute`."""
    if _call_name(call) not in SQL_CALLS:
        return False
    strings = (f" {sql.lower()} " for sql in _strings_in(call))
    return any(
        DIGEST in sql and any(word in sql for word in SQL_PREDICATE_WORDS) for sql in strings
    )


def _strings_in(call: ast.Call) -> list[str]:
    """Each string literal in the call, an f-string's literal parts joined into one."""
    joined = [node for node in ast.walk(call) if isinstance(node, ast.JoinedStr)]
    parts = {id(part) for node in joined for part in node.values}
    whole = ["".join(_literal(part) for part in node.values) for node in joined]
    plain = [
        node.value
        for node in ast.walk(call)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in parts
    ]
    return whole + plain


def _literal(part: ast.AST) -> str:
    is_text = isinstance(part, ast.Constant) and isinstance(part.value, str)
    return part.value if is_text else " "


def _is_a_column_method(call: ast.Call) -> bool:
    """`R.upload_ciphertext_digest.in_(...)`, `.is_(...)`, `.like(...)`: a predicate by method."""
    return isinstance(call.func, ast.Attribute) and _is_the_column(call.func.value)


def _offends(node: ast.AST) -> bool:
    """A predicate, a comparison or SQL that keys on the digest. A comparison counts wherever it
    is built, so `match = R.upload_ciphertext_digest == x` then `.where(match)` is caught too."""
    if isinstance(node, ast.Compare):
        return any(_names_the_digest(side) for side in (node.left, *node.comparators))
    if isinstance(node, ast.Call):
        return _keys_a_predicate(node) or _is_sql_keyed_on_it(node) or _is_a_column_method(node)
    return False


def _exempt_functions(path: Path, tree: ast.AST) -> list[ast.AST]:
    names = EXEMPT.get(path, set())
    if names is None:
        return [tree]
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in names
    ]


def digest_predicates(path: Path) -> list[int]:
    """Lines in `path` that key on the digest, outside `FR-258`'s exceptions."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    exempt = {id(node) for scope in _exempt_functions(path, tree) for node in ast.walk(scope)}
    return sorted(
        {node.lineno for node in ast.walk(tree) if id(node) not in exempt and _offends(node)}
    )


def test_the_guard_reads_the_package_it_is_meant_to() -> None:
    """Anchored on the installed package, not the working directory: an empty sweep passes."""
    assert (PACKAGE / "rca" / "workspace" / "store.py").is_file()
    assert len(list(PACKAGE.rglob("*.py"))) > 100


#: Each way a query can key on the digest. The first three are the pre-amendment code, verbatim in
#: shape: `store.py`'s retry lookup, `workspace_retention.py`'s purge join and
#: `workspace_deletion.py`'s session lookup. The rest are the forms review on this slice found an
#: earlier guard missed.
KEYED = {
    "retry lookup": (
        "select(DatasetVersionRow).where(DatasetVersionRow.owner_id == owner_id)"
        ".where(DatasetVersionRow.upload_ciphertext_digest == ciphertext_digest)"
    ),
    "purge join": (
        "select(UploadRow.upload_id).join(DatasetVersionRow, "
        "(DatasetVersionRow.owner_id == UploadRow.owner_id) & "
        "(DatasetVersionRow.upload_ciphertext_digest == UploadRow.ciphertext_sha256_hex))"
    ),
    "deletion lookup": (
        "select(UploadRow.session_id).where(UploadRow.owner_id == version.owner_id, "
        "UploadRow.ciphertext_sha256_hex == version.upload_ciphertext_digest)"
    ),
    "filter_by keyword": "query.filter_by(upload_ciphertext_digest=digest)",
    "onclause keyword": "select(U).join(R, onclause=R.upload_ciphertext_digest == U.c)",
    "indirection": "match = R.upload_ciphertext_digest == digest; select(R).where(match)",
    "raw SQL": 'database.execute(text("SELECT 1 FROM v WHERE upload_ciphertext_digest = :d"))',
    "f-string SQL": 'text(f"SELECT 1 FROM {table} WHERE " f"upload_ciphertext_digest = :d")',
    "getattr": "select(R).where(getattr(R, 'upload_ciphertext_digest') == digest)",
    "column subscript": "select(R).where(R.c['upload_ciphertext_digest'] == digest)",
    "column method": "select(R).where(R.upload_ciphertext_digest.in_(digests))",
}


@pytest.mark.parametrize("form", sorted(KEYED))
def test_the_guard_refuses_every_form_of_keying_on_the_digest(form: str, tmp_path: Path) -> None:
    """The mutation proof `FR-258` names, run through the same function the sweep runs."""
    module = tmp_path / "keyed.py"
    module.write_text(KEYED[form], encoding="utf-8")

    assert digest_predicates(module), form


def test_the_guard_admits_writing_and_reading_the_recorded_digest(tmp_path: Path) -> None:
    """Recording the digest and projecting it into a record are not keys (`FR-258`)."""
    module = tmp_path / "recorded.py"
    module.write_text(
        "row = DatasetVersionRow(upload_ciphertext_digest=version.upload_ciphertext_digest); "
        "source = AdmittedSource(ciphertext_digest=row.upload_ciphertext_digest)",
        encoding="utf-8",
    )

    assert digest_predicates(module) == []


def test_no_query_keys_on_the_ciphertext_digest() -> None:
    offending = {
        str(path.relative_to(PACKAGE)): lines
        for path in sorted(PACKAGE.rglob("*.py"))
        if (lines := digest_predicates(path))
    }

    assert offending == {}
