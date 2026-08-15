"""R3-10: the `IdentityProvider` seam and its verified-identity type.

**What the seam is for.** `KHEPRI-DEC-018` §6: provider concepts must not spread into Khepri's
domain, authorization, organization, membership, or isolation logic, and a narrow internal seam
contains them. It exists for *vendor containment*, not to build a provider-switching framework.

**What it may expose, exhaustively:** whether a request carries a verified identity, and the stable
provider subject with its issuing provider. §6 says "it exposes nothing else. Khepri business
authority is not expressible through it, so a provider cannot assert authority even in error."

That last clause is the property this suite exists to hold, and it is structural rather than
behavioral. A seam that *could* carry a role is one where a future adapter will eventually put one;
`test_a_verified_identity_carries_exactly_two_fields` makes that a test failure instead.

**No adapter here.** `R3-11` owns any concrete provider and is blocked on an admission under §5 --
per the merged Clerk evaluation, four vendor-evidence gates are outstanding. This slice is
provider-neutral, and `TestNoVendorLeaks` asserts that no vendor name appears anywhere in it.
"""

from __future__ import annotations

import ast
import pathlib
from dataclasses import FrozenInstanceError, fields, is_dataclass
from typing import get_type_hints

import pytest

from khepri.rca.identity import IdentityProvider, VerifiedIdentity

#: `KHEPRI-DEC-018` §4's refused claims, verbatim. A provider commonly emits these; Khepri must not
#: read them for any authorization purpose, and the seam must not be able to carry them at all.
REFUSED_CLAIMS = (
    "organization",
    "role",
    "permissions",
    "membership",
    "can_act",
    "resource ownership",
)

PROVIDER = "example-provider"
SUBJECT = "user_2abcDEF"

#: Identity vendors the seam must not be written toward before one is admitted under §5.
VENDORS = ("clerk", "auth0", "okta", "cognito", "firebase", "workos", "keycloak")


def _identity_source() -> str:
    return pathlib.Path("src/khepri/rca/identity.py").read_text(encoding="utf-8")


class TestTheVerifiedIdentity:
    def test_a_verified_identity_carries_exactly_two_fields(self) -> None:
        """`KHEPRI-DEC-018` §6: the stable provider subject, and the provider that issued it.

        **An allowlist, not a denylist**, for the reason `R3-08` records: checking that no field is
        *named* `role` does not catch one named `claims` or `context` carrying the same thing. The
        exact set means any addition fails here and has to be argued against §6.
        """
        assert {field.name for field in fields(VerifiedIdentity)} == {
            "provider",
            "provider_subject",
        }

    def test_both_fields_are_plain_strings(self) -> None:
        """A provider-shaped object in either field would smuggle vendor types past the seam,
        which is exactly what §6 confines behind the adapter."""
        hints = get_type_hints(VerifiedIdentity)
        assert hints["provider"] is str
        assert hints["provider_subject"] is str

    def test_it_is_frozen(self) -> None:
        """A mutable verified identity could be edited after verification, so what was checked
        and what is used would be different objects."""
        identity = VerifiedIdentity(provider=PROVIDER, provider_subject=SUBJECT)
        with pytest.raises(FrozenInstanceError):
            identity.provider_subject = "someone-else"  # type: ignore[misc]

    def test_it_is_not_sealed(self) -> None:
        """Deliberately a plain frozen dataclass, following `StoredSession` rather than `Session`.

        `records.py`'s two-door rule governs records Khepri *mints* -- creation validates,
        reconstruction preserves. A verified identity is neither: it is an inbound fact an adapter
        reports, carrying no invariant Khepri allocates. Sealing it would add ceremony without a
        protected invariant, and would imply this package constructs provider identities.
        """
        assert is_dataclass(VerifiedIdentity)
        from khepri.rca.records import Sealed

        assert not issubclass(VerifiedIdentity, Sealed)

    def test_it_is_not_an_account_identifier(self) -> None:
        """The seam stops at `(provider, subject)`. Mapping to an account is a local lookup that
        `R3-04` owns -- `R3-09` §2.1 requires it be local, so a provider outage cannot make an
        already-authenticated request unresolvable."""
        assert "account_id" not in {field.name for field in fields(VerifiedIdentity)}


class TestTheSeamCannotExpressAuthority:
    def test_no_field_names_a_refused_claim(self) -> None:
        """`KHEPRI-DEC-018` §4. Belt to the allowlist's braces: this one names the specific
        claims the decision lists, so a violation reports *which* rule it broke."""
        names = {field.name.lower() for field in fields(VerifiedIdentity)}
        for claim in REFUSED_CLAIMS:
            token = claim.replace(" ", "_")
            assert not any(token in name for name in names), f"the seam can carry `{claim}`"

    def test_the_protocol_returns_only_a_verified_identity_or_nothing(self) -> None:
        """`verify` answers "is there a verified identity, and whose" and nothing more.

        `VerifiedIdentity | None` is the whole vocabulary: `None` is "no verified identity",
        which is the "whether the request carries one" half of §6. A richer return type is how a
        provider's claims would arrive despite §4.
        """
        hints = get_type_hints(IdentityProvider.verify)
        assert hints["return"] == VerifiedIdentity | None

    def test_the_module_mentions_no_refused_claim_as_a_field(self) -> None:
        """The decision's prohibition is on *use for authority*, so the module may discuss these
        words in its docstrings -- and does. What it must not do is declare one. Read from the
        AST, so prose is not mistaken for structure (`R3-08`'s correction)."""
        declared: set[str] = set()
        for node in ast.walk(ast.parse(_identity_source())):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                declared.add(node.target.id.lower())
        for claim in REFUSED_CLAIMS:
            token = claim.replace(" ", "_")
            assert not any(token in name for name in declared), f"`{claim}` is declared"


class TestTheProtocol:
    def test_any_object_with_verify_satisfies_the_seam(self) -> None:
        """Structural, not nominal. An adapter need not import or subclass anything from here,
        which is what keeps `R3-11`'s vendor code from reaching back across the boundary."""

        class Adapter:
            def verify(self, credential: str) -> VerifiedIdentity | None:
                return VerifiedIdentity(provider=PROVIDER, provider_subject=SUBJECT)

        assert isinstance(Adapter(), IdentityProvider)

    def test_an_object_without_verify_does_not_satisfy_it(self) -> None:
        class NotAnAdapter:
            def check(self, credential: str) -> None: ...

        assert not isinstance(NotAnAdapter(), IdentityProvider)

    def test_the_protocol_has_exactly_one_method(self) -> None:
        """§6: "it exposes nothing else". A second method is a second thing a provider could be
        asked, and the seam's narrowness is the containment."""
        members = {
            name
            for name in vars(IdentityProvider)
            if not name.startswith("_") and callable(getattr(IdentityProvider, name, None))
        }
        assert members == {"verify"}


class TestNoVendorLeaks:
    def test_the_module_imports_no_third_party_package(self) -> None:
        """§6: vendor SDK types, request and response shapes, and error types stay behind the
        adapter, and no module outside it may import them. The seam is where that is easiest to
        violate and hardest to notice, so it is asserted rather than trusted."""
        imported = _imported_modules(_identity_source())
        allowed_roots = {"__future__", "dataclasses", "typing", "khepri"}
        for name in imported:
            root = name.split(".")[0]
            assert root in allowed_roots, f"the seam imports `{name}`"

    def test_no_vendor_appears_in_declared_code(self) -> None:
        """`R3-11` admits a provider; `R3-10` must not anticipate which one.

        The same discipline `khepri.infra` follows for `KHEPRI-DEC-007`: the platform path encodes
        limits, never the chosen values. A vendor in the *code* would make the seam that vendor's
        shape before any admission gate was cleared.

        **Docstrings are exempt, and that exemption is the point rather than a loophole.** This
        module cites the merged provider evaluation to explain *why* no vendor is admitted yet --
        provenance for the neutrality, not a dependency on it. An earlier version of this test
        matched raw source and failed on that citation; deleting the citation to satisfy it would
        have removed the reasoning while leaving the seam equally neutral. So the check reads
        identifiers, string literals, and imports -- the places a vendor could actually bind.
        """
        bound = _bound_names(_identity_source())
        for vendor in VENDORS:
            assert not any(vendor in name for name in bound), f"the seam binds `{vendor}`"

    def test_no_vendor_is_named_outside_a_docstring(self) -> None:
        """The complement: a vendor in a comment is also not code, but it is a signal that the
        seam is being written toward one provider. Comments are checked because they are where an
        anticipatory `# Clerk returns ...` would land."""
        for line in _identity_source().splitlines():
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue
            for vendor in VENDORS:
                assert vendor not in stripped.lower(), f"a comment names `{vendor}`"


def _bound_names(source: str) -> set[str]:
    """Every identifier and string value the code actually binds, excluding docstrings.

    Docstrings are the one place this module legitimately names a vendor -- citing the merged
    provider evaluation is provenance for the seam's neutrality, not a dependency on it. A
    docstring is a bare string *expression statement*, so excluding `ast.Expr` bodies separates
    prose from a real string value without needing to compare text.
    """
    tree = ast.parse(source)
    prose = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            names.add(node.attr.lower())
        elif isinstance(node, ast.alias):
            names.add(node.name.lower())
        elif isinstance(node, ast.arg):
            names.add(node.arg.lower())
        elif isinstance(node, ast.ClassDef | ast.FunctionDef):
            names.add(node.name.lower())
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node not in prose
        ):
            names.add(node.value.lower())
    return names


def _imported_modules(source: str) -> set[str]:
    """Every module name this source imports, however it spells the import.

    Duplicated deliberately rather than imported from `test_rca001_session_security_evidence`:
    a test helper shared between suites couples them, and one suite's refactor then silently
    changes what the other asserts.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names
