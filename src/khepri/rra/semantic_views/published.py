"""Published version history and exact-version resolution (`SV1-06`).

`RRA-014` `FR-143` and `FR-134`'s immutability.

`FR-143`: "Requests name an exact version; supported historical readers return
that immutable definition and unsupported versions refuse. **No `latest` alias
or silent upgrade exists.**"

**There is no default and no alias, and that is a structural property here rather
than a promise.** `resolve` takes the version as a required argument, so a
caller cannot omit it; the history is keyed by the exact version string, so
`latest` is a key that is simply absent; and an unpublished version reaches
`CAUSE_UNKNOWN_VERSION` by the same path as any other miss. Nothing in this
module maps one version onto another, which is what a silent upgrade would be.

**The digest table is the point of this module, and it is a second record on
purpose.** `FR-134` makes a published definition immutable, and the trap the
`SV1` plan names is that a slice can "fix" one in place while every test still
passes -- because the tests read the same object the edit changed. An
immutability check whose expected value is derived from the thing it checks is a
tautology. `PUBLISHED_DIGESTS` therefore records, as literals, the content
digest each version was published with. Everywhere else in this package a second
literal would be the "second truth" `FR-135` forbids; here it is the independent
witness without which immutability cannot be checked at all.
"""

from __future__ import annotations

import hashlib
from dataclasses import fields

from khepri.rra.profiling import canonical_json
from khepri.rra.semantic_views.contracts import SemanticViewDefinition
from khepri.rra.semantic_views.refusals import (
    CAUSE_UNKNOWN_VERSION,
    CAUSE_UNKNOWN_VIEW,
    ViewRefusal,
)
from khepri.rra.semantic_views.registry import UnknownView, define_view, view_ids

__all__ = [
    "PUBLISHED_DIGESTS",
    "definition_digest",
    "published_history",
    "published_versions",
    "resolve",
]

#: The content digest each published version was published with, written down
#: rather than computed from the registry. See the module docstring: this is the
#: one place a literal is not a second truth but the only possible witness.
#:
#: A version is added here when it is published and never edited afterwards. An
#: edit to a published definition changes its digest and fails
#: `test_every_published_definition_still_matches_its_published_digest`, which is
#: exactly the failure `FR-134` asks for.
PUBLISHED_DIGESTS: dict[str, str] = {
    "sv1.basket.v1": "0f40b6e0294f01d0d47b6758c613e4d6fbb22f470aa83c21e3f7e6b3b5ed510d",
    "sv1.branch_performance.v1": "64a34d0b0d1de5914b2961f068c91d8a3826e1b01f167586189d1533dac4dbbe",
    "sv1.concentration.v1": "bc3d3f6b9faccf0a84f1d41a32aefbd0e27fba37ebda2cb77bf4fd35c1a4f070",
    "sv1.executive_overview.v1": "3d124a2bdad3906f738397d2ede414c8c943dee854ed69537901707fd76826e8",
    "sv1.metric_availability.v1": (
        "2a00fefef2390c0d7ba777f7a25fd44b22060f513b082f61b5c2d02e7aff2817"
    ),
    "sv1.period_comparison.v1": "d172001a9988bb9bad5161f04f511f7fb3aae00e30c56755c6252634dd4d98bd",
    "sv1.product_category.v1": "2f78104649310de8e1f39eea4730777fdc33806badf0fca185b634db34348178",
    "sv1.report_evidence.v1": "c56dd758dad9aa5931f3586f75b9d85946cdac9f7b5bd1be148f53d0ff9dc0c7",
}


def _document(definition: SemanticViewDefinition) -> dict[str, object]:
    """One definition as a plain document, in a stable field order.

    Derived from the record's own fields rather than listed, following
    `contracts._semantics`: a contract field added to the definition joins the
    digest with no edit here, which is what makes the digest cover the whole
    record rather than the part someone remembered.
    """
    return {field.name: _plain(getattr(definition, field.name)) for field in fields(definition)}


def _plain(value: object) -> object:
    """A tuple as a list, so the document serializes; anything else unchanged."""
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def definition_digest(definition: SemanticViewDefinition) -> str:
    """The content digest of one published definition.

    `canonical_json` is the repository's own serializer -- sorted keys, no
    spaces -- so the digest depends on the record's content and not on how a
    Python version happened to order a dict.
    """
    return hashlib.sha256(canonical_json(_document(definition)).encode()).hexdigest()


def published_versions(view_id: str) -> tuple[str, ...]:
    """Every version of one view, oldest first, or `()` for an unpublished view.

    A tuple rather than a set: `FR-143`'s "supported historical readers" is a
    sequence claim, and append-only is only checkable against an order.
    """
    try:
        definition = define_view(view_id)
    except UnknownView:
        return ()
    return (definition.view_version,)


def published_history() -> dict[str, tuple[str, ...]]:
    """Every published view and its versions, oldest first.

    Built from the registry rather than listed beside it, so a ninth view cannot
    be published without appearing here. The registry publishes one version per
    view today; this shape is what lets a second version be added without
    changing `resolve`'s signature or any caller.
    """
    return {view_id: published_versions(view_id) for view_id in sorted(view_ids())}


def resolve(view_id: str, view_version: str) -> SemanticViewDefinition | ViewRefusal:
    """The definition published under exactly this identity, or a governed refusal.

    Both arguments are required. `FR-143` admits no `latest` alias and no silent
    upgrade, so there is nothing to default to: a caller that does not know which
    version it wants is asking a question this module cannot answer, and the
    absence of a default is what makes that structural rather than documented.

    `latest` is not special-cased. It refuses because it is not a published
    version string, by the same path as any other unpublished version -- a branch
    naming it would be the first half of the alias `FR-143` forbids.
    """
    if view_id not in view_ids():
        return ViewRefusal(CAUSE_UNKNOWN_VIEW)
    if view_version not in published_versions(view_id):
        return ViewRefusal(CAUSE_UNKNOWN_VERSION)
    return define_view(view_id)
