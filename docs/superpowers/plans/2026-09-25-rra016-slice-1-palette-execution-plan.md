# RRA-016 slice 1 — the journey declares the §16.5 palette

**Specification:** `RRA-016` (registry `active`), palette requirements `FR-220`–`FR-222` only.
`RRA-010` remains `active`. Composition (`FR-223`–`FR-226`) and hero (`FR-227`–`FR-229`) are later
slices; the hero is its own slice after this one (`RRA-016` §Implementation preconditions 2).

## Scope

Files this slice changes, each admitted by `RRA-016` §Scope:

- `src/khepri/rra/journey/assets/journey.css` — `:root` values and the rules that consume them.
- `tests/test_rra016_journey_palette.py` — new.
- `tests/test_r801_shell_tokens.py` — one cross-specification test change, named below.

No template, script, copy key, route, handler, allowlist entry, shell stylesheet or runtime module
changes.

## Role mapping

Every journey colour becomes a custom property whose value is a master specification §16.5 row,
and no rule below `:root` carries a colour literal. Roles are mapped by computed contrast, not by
name:

| Journey property | §16.5 row | Why this row |
|---|---|---|
| `--paper` | `surface-canvas #FBF9F6` | the page ground |
| `--surface` | `surface-card #FFFFFF` | header, step nav, inputs |
| `--ink` | `ink #16212B` | body text, 15.5:1 on canvas |
| `--muted` | `ink-muted #55616C` | secondary text, 6.0:1 on canvas |
| `--line` | `border-strong #DED7CC` | rules and dividers (decorative) |
| `--accent`, `--accent-dark`, `--focus` | `gold-ink #7A5A17` | `gold-500` is ~2.3:1 as text; `gold-ink` is 6.0:1 on canvas, 6.4:1 under white text |
| `--danger` | error ink `#B0392F` | 5.2:1 on its own fill |
| `--journey-danger-surface` / `--journey-danger-border` | error fill `#FBE9E7` / border `#F2DAD6` | the error summary's triplet |
| `--journey-line-subtle` | `border-inner #EFE9E0` | step-nav and table hairlines |
| `--journey-sunken` | `surface-sand #F4EEE4` | the drop zone's ready ground |
| `--journey-accent-surface` | `gold-tint #F6EBD6` | the drop zone while dragging |
| `--journey-ink-secondary` | `ink-secondary #6B7580` | text-input boundary (4.7:1 on white, over the 3:1 non-text floor the old `#cfd6de` missed at 1.4:1) and disabled-button text |

`--ready` is removed: no journey rule consumes it, and an unconsumed token is the defect
`RRA-010`'s type-scale slice removed rather than relocated. New names carry the `journey-` prefix
so `FR-222` ownership is readable from the name; `shell.css` already declares bare §16.5-style
names (`--surface-page`, `--line-subtle`).

`FR-221` is already true and stays so: `.refusal-summary` is `--muted` shape-and-italic with no
error paint (`test_rra_journey_accessibility.py` pins it), and the error summary states its
state in words.

## The navy reading (recorded for the owner)

`FR-220` says "a dark navigation or chrome region carries the navy". The `/beta` shell renders a
header and a step nav and no rail; the handoff's TopBar is white and its navy region is the
SideNav, which the journey does not render. `FR-223` forbids adding an element the journey does
not already render. So this slice binds the clause's **negative** half — no navy content surface,
no dark theme, no theme control — and paints no region navy. Where, if anywhere, the journey's
chrome carries the navy is a composition question for the `FR-223` slice, under the handoff.

## Cross-specification test change: `test_r801_shell_tokens.py`

`test_shell_introduces_no_colour_outside_the_shipped_palette` (`RCA-010` Verification) admits a
shell colour if it appears anywhere in `journey.css`. Six shell values rely on that alone:
`#1d6b45`, `#6d201b`, `#9a2d26`, `#d9a49f`, `#e3ded1`, `#faece9`. None is a §16.5 value, so
`FR-220` removes them from `journey.css` and the shell test would go red with no shell change.

The subtraction stops reading `journey.css` and reads a frozen, enumerated set of exactly those
six, with provenance ("the values `journey.css` shipped at `cbeecf4`, before `RRA-016` `FR-220`").
This is **strictly stronger**, not a weakening: before, any colour added to `journey.css` silently
widened what the shell might use; now nothing does. The `#abcdef` positive control is kept.
`_ORPHAN_BASELINE` is untouched — removing literals passes its subset check.

**Residual, not this slice's:** `shell.css` still declares those six non-§16.5 values. That is an
`RCA-010` item for a later issue.

## Tests (RED first)

`tests/test_rra016_journey_palette.py`:

1. §16.5 is parsed from `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md` between `### 16.5` and `## 17`
   as the independent source, never from `shell.css`; the distinct-value count is pinned by hand
   (warning ink equals `gold-ink`, so it is one less than the row count).
2. Every hex in `journey.css` (comments stripped) is a §16.5 value — with an injected-literal
   positive control.
3. No colour literal below `:root`; no functional or named colour in a colour declaration — with
   positive controls.
4. Each journey property equals the §16.5 row the table above names, looked up by row name.
5. Computed static contrast for every ink/ground pair the rules draw.
6. Browser, both languages, 1440 / 1024 / 390, every step: computed text contrast over the
   effective background, no page-level horizontal overflow, 44px targets.

## Gates

`uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest` (counts line read; browser
tests must not skip).
