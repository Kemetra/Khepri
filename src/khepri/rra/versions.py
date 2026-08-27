"""Which governed versions may be combined in one published result.

`RRA-004` requires that a new input, mapping, formula, population,
interpretation, correction, or serialized shape create a new recorded version
and stable identity. That rule is about *producing* a version. This module
enforces its other half: that the versions a result actually **combines** were
authorized to appear together.

Nothing enforced it before. `packages.py` stamped `PACKAGE_VERSION`,
`FORMULA_VERSION` and `MAPPING_VERSION` from three independent constants, and
`bundle._FAMILIES` dispatched `comparison`, `growth`, `basket` and
`concentration` unconditionally, each stamping its own `rra008.*` constant
without ever consulting the package's `formula_version`. So moving one version
ahead of its consumers published changed numbers under unmoved identities --
the precise defect `RRA-004` forbids, in the window between two slices rather
than in either slice's own code.

**An explicit table, and deliberately not a comparison.** These identifiers are
independent namespaces: `rra003.mapping.v3`, `rra004.formula.v2` and
`rra008.basket.v2` share a numbering convention and nothing else, so their
suffixes define no ordering anything could compare. Three further reasons the
table form is the right one, recorded so a later reader does not "simplify" it
into a predicate:

- A "newer than" rule guards one direction only. Once a family reached `v2`,
  "refuse when the formula is newer" would happily stamp a successor family
  identity onto a package still carrying `rra004.formula.v1`.
- An unrecognised version's handling would be undefined under a comparison,
  where a table refuses it by construction -- membership is the whole test.
- `RRA-008` frames its own contract the same way: its `v2` families consume
  "the exact `rra003.mapping.v3`, `rra004.package.v3`, and `rra004.formula.v2`
  changes". Exact, not "at least".

**Fail closed.** Both functions answer a membership question and nothing else.
There is no default-admit branch, no fallback, and no parsing of a version
string into parts that could be ranked.

**Two seams, refused at different scopes.** The caller decides how, because the
right refusal differs: a mapping/package/formula mismatch is caught while the
package is built and refuses the package, while a family/formula mismatch must
refuse only that family, leaving independently answerable results intact as
`RRA-008` requires.
"""

from __future__ import annotations

# Reason codes for the two seams. Governed strings, carried into audit evidence
# and into the bilingual customer wording that ships with them.
REASON_PACKAGE_VERSION_UNADMITTED = "package_version_pairing_unadmitted"
REASON_FAMILY_VERSION_UNADMITTED = "family_version_pairing_unadmitted"


# Every admitted (mapping, package, formula) triple. A slice adds its own row
# when it lands; it never edits a row another slice put here, because that row
# names a combination already published under a stable identity.
ADMITTED_PACKAGE_PAIRS: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("rra003.mapping.v2", "rra004.package.v2", "rra004.formula.v1"),
        # `V-package`'s own row, and the only one it adds. The formula stays
        # `v1` because `rra004.formula.v2` does not exist until `V-formula`;
        # naming it here would publish that identity early.
        ("rra003.mapping.v3", "rra004.package.v3", "rra004.formula.v1"),
        # `V-formula`'s own row, and the only one it adds. **No family row
        # accompanies it**: each `RRA-008` family adds its own
        # `(formula.v2, family.v2)` pair when it lands, so all four refuse
        # from here until `V-comparison`. The refusing set is largest at
        # this commit and `V-concentration` empties it. That blackout is
        # the designed window, not a gap to close early.
        ("rra003.mapping.v3", "rra004.package.v3", "rra004.formula.v2"),
    }
)


# Every admitted (formula, family) pair, for the four `RRA-008` families.
ADMITTED_FAMILY_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("rra004.formula.v1", "rra008.comparison.v1"),
        ("rra004.formula.v1", "rra008.growth.v1"),
        ("rra004.formula.v1", "rra008.basket.v1"),
        ("rra004.formula.v1", "rra008.concentration.v1"),
        # `V-comparison`'s own row. Three families still refuse after it;
        # each adds its own pair when it lands.
        ("rra004.formula.v2", "rra008.comparison.v2"),
    }
)


def admits_package(
    *,
    mapping_version: str,
    package_version: str,
    formula_version: str,
) -> bool:
    """Whether these three versions were authorized to be combined."""
    return (mapping_version, package_version, formula_version) in ADMITTED_PACKAGE_PAIRS


def admits_family(*, formula_version: str, family_version: str) -> bool:
    """Whether this `RRA-008` family may publish over this core formula."""
    return (formula_version, family_version) in ADMITTED_FAMILY_PAIRS
