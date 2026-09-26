# #572: journey presentation fixes and the shell palette residual

Presentation only. No route, copy, figure, governed word or dependency changes.

## Scope and authority

| Item | Files | Authority |
|---|---|---|
| 1. The currency field is red at rest | `rra/journey/assets/journey.css` | `RRA-010` §Invariants, `RRA-016` (journey presentation) |
| 2. Date inputs show no journey focus ring | `rra/journey/assets/journey.css` | `RRA-010` focus floor; owner decision on #572, 2026-09-26 |
| 3. The shell declares six non-§16.5 values | `rra/journey/assets/shell.css` (tokens only) | `RCA-010` §Scope; master spec §16.5 |

## Findings

1. `#contract-currency-code:invalid:not(:placeholder-shown)` matches from first paint: the input is
   `required` and has no placeholder. **Fix:** use `:user-invalid`, which Chromium 149 matches only
   after the operator edits and leaves the field, or tries to submit.
2. The issue's premise is partly stale. On Chromium 149, `:focus-visible` *does* match the host
   while a date segment has focus. The failing stop is the fourth: the calendar-picker button
   inside the shadow tree, where `:focus-visible` stops matching the host. **Fix:** paint the
   journey ring on `input[type="date"]:focus`, which matches while any inner part holds focus.
   Native inputs are kept, as the owner decision requires.
3. Of the six residual values, only `--danger` has a consumer (`.invitation-warning`).
   `--danger-border`, `--danger-surface`, `--danger-ink`, `--ready`, `--track` and the two derived
   `--ready` companions have none. **Fix:** delete the unused tokens and move `--danger` to the
   §16.5 error ink `#B0392F`, which is 5.6:1 on the card surface.

## Tests (RED first)

- `test_rra016_journey_palette`: the date-input exemption is removed from the focus-ring scan.
  Also a new browser test: the currency border is 1px at rest and 2px after a malformed entry.
- `test_rra003_journey_source_contract`: the rule is `:user-invalid` and never `:placeholder-shown`.
- `test_r801_shell_tokens`: the palette check admits `_SUPPLIED` (§16.5) only. Removed:
  `_JOURNEY_SHIPPED`, `_DERIVED` and the derivation tests, whose tokens no longer exist. The
  positive control now also refuses the retired `#9a2d26` and `#1d6b45`.

## Not changed

`docs/product/KHEPRI_DESIGN_LANGUAGE.md` §2.3 still lists the pre-handoff values. That table
predates §16.5, which supersedes it for colour values (its accent is also the retired blue), so it
is left as history rather than edited in a presentation slice.
