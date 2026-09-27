# Khepri v2 — North Star component changes (for the code repo)

Source of truth: `templates/north-star-flagship/NorthStarFlagship.dc.html`. Visual spec: `NorthStarSystem.dc.html` (same folder).
Apply in `@khepri/ds`, then re-sync with `/design-sync`. Status: **proposal, awaiting owner approval.**

## Tokens
- Add: `--k-paper #F6F2EA`, `--k-raised #FBF9F4`, `--k-band #EEE7DA`, `--k-sand #ECE3D2`, `--k-ink #16140F`, `--k-ink-2 #3D3831`, `--k-muted #5C554A`, `--k-compare #9A8F7C`, `--k-pos #276B4E` / `--k-pos-soft #E4EEE7`, `--k-neg #B03D25` / `--k-neg-soft #F6E4DD`, `--k-gold #A07A3A` / `--k-gold-text #7A5A22`.
- Rules: `--k-rule-strong #16140F`, `--k-rule #C9BEAA`, `--k-hairline #DED5C5`. Radius: controls 3px, menus 4px, tags 2px.
- Retire `--k-gold-gradient` (also clears the unclassified-token warning). Shadow only on floating layers: `0 14px 36px rgba(22,20,15,.14)`.
- Fonts: add Noto Naskh Arabic (display, 500–700) and IBM Plex Sans Arabic (text/data, 300–700); `font-variant-numeric: tabular-nums`.

## Keep (6)
KhepriLogo (pending decision), TaskItem, FileTypeIcon, LogConsole, Avatar, AvatarGroup.

## Refine (31)
KhepriProvider, Icon, Button (primary = ink), IconButton, LinkButton, SuggestionCard (→ next-step item), LineChart, BarChart, ChartLegend, DataTable (sand header band, group rows + subtotals, 54px rows, end-aligned numerics, hover, drill cue, outlier tint), PrimaryCell, StatusPill (dot + text), ConfidenceBadge (text + value + bar, same thresholds), CountBadge (finding reference ring), KeyValueList, ProgressBar, Tag, EmptyState, FileRow, Tabs, SegmentedControl, Stepper, Select (+ two-line context variant), Toggle, Checkbox, TextField, TextArea, SearchInput, Field, SelectableCard, Dropzone.

## Replace / redesign (9)
AppShell + TopBar → ink app bar + context band + centred canvas (max 1560px). PageHeader → context-band header. Card → Section. StatTile → KPI Register. FindingCard → Finding (signal / interpretation, confidence, sources, link). AnalysisCard → ruled list row. ProgressRing → figure + bar. CategoryTile → ruled filter list.

## Not needed (3, owner to confirm)
IconBadge, Sidebar (analysis views), DonutChart.

## Unchanged semantics
All StatusPill statuses and labels, confidence thresholds, one-primary-per-view, RTL/LTR via logical properties, `<bdi>` for mixed values, time axes left→right.

## Open decisions
Primary colour (ink vs gold), logo, exact brand hex values, display face and English headline face, digit system, retirement of Sidebar/DonutChart/ProgressRing, status tone mapping, caveat/refusal patterns (none exist in the library yet).
