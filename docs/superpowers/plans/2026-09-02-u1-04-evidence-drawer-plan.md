# U1-04 — the evidence drawer's structure

**Authority:** active `RRA-012`, FR-096, FR-096a, FR-097, FR-098, and the FR-095a labels they
need. **Scope:** `U1-04`'s *structure* only. **Not in this plan:** the drawer's catalog data
**supply**, which `RRA-012`'s Scope note defers to its own artifact because every surface in
Scope is a stored artifact and a catalog read changes the materialization path.

**Status:** bounded plan. Its RED tests land with it (`tests/test_u1_04_evidence_drawer.py`),
which is what §15 requires before `U1`'s row moves to `READY_FOR_IMPLEMENTATION`.

---

## Three checks against the tree, run before this plan was written

### 1. What the drawer will be handed already has a shape — `_cited_figure`

`report_api.py:1014` builds the per-figure projection `RRA-011`'s citation route serves:
`citation_id`, `metric`, `name`, `formula_version`, `definition`, `unit_kind`, `precision`,
`inputs`. Its docstring records the load-bearing fact for FR-096a: for a **derived** analysis
figure — comparison, growth, basket, concentration — `precision` and `inputs` are **absent, not
empty and not recomputed**, because re-deriving them is what `RRA-011`'s Exclusions forbid.

**Resolution: the drawer macro takes that mapping as-is** and reads only the keys it renders.
The deferred supply slice then hands it the projection it already produces, and no second shape
is invented here. The RED fixture asserts its key set equals `_cited_figure`'s, so the fixture
cannot drift from the projection it stands in for.

### 2. Coverage in the drawer is package-level, and the catalog says so

`CitationEvidenceResponse` carries `coverage_manifest_identity` and `coverage_signatures`
**at package scope** (`report_api.py:327`), read from the package and not from the figure. FR-097
forbids a per-figure population or basis, and `RRA-011`'s Outcome records that a `Fact` carries
no population identifier. So the drawer's coverage field renders the package's coverage
identity it is given, labelled as coverage — and the macro has no population or basis input at
all. A test hands it a mapping carrying `population` and `basis` keys and proves neither value
reaches the page.

### 3. Keyboard behaviour without a script — `<details>`/`<summary>`

`html.py:29` records that **no JavaScript is bundled at all**, and
`test_rra006_html_surface.py:382` asserts `<script>` never reaches the document. FR-098 needs
the drawer reachable by keyboard, dismissible by keyboard, and returning focus to its opener.
The native disclosure element gives all three with no script: `<summary>` is focusable and
toggles on Enter and Space; closing it is the same key on the same element; and since the
opener never loses focus when toggled from the keyboard, "return focus to the opener" holds
by construction rather than by a handler. The `<summary>` is the drawer's **only** control —
nothing inside it carries `tabindex`, so the drawer body adds no focus stops.

**What this does not give:** closing on Escape from inside the body. That needs a script, and
no active specification admits one on this surface. Recorded as a known limit, not smoothed
over; the print surface, which extends the same template, is unaffected because a printed
drawer is simply open.

---

## What is being built

One macro, `evidence_drawer(given, chrome)`, in `_components.html.j2`, beside the seven
`U1-02` components, and the FR-095a labels it names.

| Field (FR-096) | Reads | Renders through |
|---|---|---|
| Definition | `given.definition` | text, labelled `chrome.component.definition` |
| Governed version | `given.formula_version` | **the `U1-02` `version_label` macro** |
| Inputs | `given.inputs` | a list; **`None` → the unavailable state** |
| Coverage | `given.coverage_manifest_identity` | text, labelled `chrome.component.coverage`; `None` → unavailable |
| Citation | `given.citation_id` | **the `U1-02` `evidence_link` macro** |

Reusing `version_label` and `evidence_link` is FR-092: a drawer rendering a version its own way
would be the second source of presentation truth that requirement refuses.

**The unavailable state (FR-096a)** is one chrome label, `chrome.component.unavailable`,
rendered in the field's `<dd>` with `data-state="unavailable"`. It is **not** the refusal label
and the drawer carries no `refused` class anywhere: an absent field is the catalog declining to
state something, not a refusal.

**Chrome labels added to `COMPONENT_CHROME`** (FR-095a, both languages, under the existing
import-time assertion): `drawer_open` (the control's text — "Evidence for this figure"),
`definition`, `inputs`, `unavailable`. `coverage` and `version_label` already exist from `U1-02`;
`chrome.citation` already exists in `_CHROME`. No word here describes a metric, refusal, caveat,
population or version.

**Structure:**

```
<details data-component="evidence-drawer" class="drawer">
<summary class="drawer__opener">{{ chrome.component.drawer_open }}</summary>
<dl class="drawer__fields"> … five <div><dt/><dd/></div> … </dl>
</details>
```

**Stylesheet:** `report.css` gains `.drawer`, `.drawer__opener`, `.drawer__opener:focus-visible`
and `.drawer__fields` rules, logical properties only. The print stylesheet is untouched.

## What is deliberately NOT built here

**The drawer is not placed on any page in this slice**, and a guard test says so. Placing it
today would render every field in its unavailable state — not because the catalog declined to
state them, but because nothing supplies them yet — and that misstates FR-096a to every reader.
The macro exists, is proven against the projection's real shape, and waits for the supply slice
to hand it data. `test_no_surface_places_the_drawer_before_its_supply_exists` passes now and is
**deleted by the supply slice**, which is the one PR entitled to remove it.

## RED tests — the deliverable

In `tests/test_u1_04_evidence_drawer.py`, strict-xfail like `U1-02`'s, each failing now because
the macro and its labels do not exist. Every test drives the macro through the production
environment with the real `_CHROME`, the discipline `U1-02`'s `render_macro` set.

1. `test_the_drawer_component_exists` — the macro is importable from `_components.html.j2`.
2. `test_the_drawer_renders_every_given_field[5]` — parametrized over the five FR-096 fields.
3. `test_an_absent_field_renders_the_unavailable_state` — a derived-family mapping with
   `inputs: None` renders the governed word, and no `<dd>` in the drawer is empty. FR-096a.
4. `test_an_absent_field_is_not_labelled_a_refusal` — the unavailable word is not the refusal
   label, and no `refused` class appears. FR-096a's last sentence.
5. `test_the_drawer_shows_no_per_figure_population_or_basis` — extra `population`/`basis`
   keys in the mapping never reach the markup. FR-097.
6. `test_the_drawer_opener_is_the_only_control_and_needs_no_script` — a `<summary>` opener,
   no `tabindex` in the body, no `<script>`. FR-098 as check 3 delivers it.
7. `test_the_drawer_renders_in_both_languages` — Arabic chrome carries Arabic script. FR-099.
8. `test_the_drawer_reuses_the_version_label_and_evidence_link` — FR-092.
9. `test_the_drawer_chrome_labels_exist_in_both_languages` — the four new keys, both languages.
10. `test_the_fixture_matches_the_projection_the_drawer_will_be_handed` — the fixture's key set
    equals `_cited_figure`'s, so check 1's shape cannot drift silently.

Plus the non-RED guard, `test_no_surface_places_the_drawer_before_its_supply_exists`.

## Sequence

1. Land this plan and its RED tests. `U1`'s §16 row moves to `READY_FOR_IMPLEMENTATION`.
2. Implement the macro, the four labels, and the stylesheet rules; remove the xfail markers.
3. The supply slice — under its own authority, not this one — threads the projection through
   `build_context`, places the drawer beside each figure in the evidence region, and deletes
   the placement guard.

## Out of scope, and why

- **Catalog supply** — `RRA-012` Scope note 2; a materialization-path change.
- **Escape-to-close** — needs a script no active specification admits on this surface.
- **Journey adoption** — `RRA-010`:88.
- **`U1-03`, `U1-05`, `U1-06`, `U1-07`** — excluded from `RRA-012`, still `BLOCKED`.
