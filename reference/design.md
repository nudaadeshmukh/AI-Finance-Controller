---
version: alpha
name: recon-dashboard-design
description: A financial reconciliation dashboard adapted from ClickHouse's high-contrast database-interface language, inverted to a white canvas. Near-black ink typography in confident Inter, electric yellow as the singular brand accent reserved for primary actions and the "reviewed" moment, and a new data-dense layer — status badges, arithmetic proof tables, and a reconciliation waterfall — built to match the existing flat, bordered, single-accent system. The yellow's scarcity at the element level is preserved; it never appears on a status badge or a money figure, only on primary actions and emphasis.

colors:
  primary: "#d4c700"
  primary-active: "#b8ad00"
  primary-disabled: "#f0edc0"
  ink: "#0a0a0a"
  body: "#3a3a3a"
  body-strong: "#1a1a1a"
  muted: "#767676"
  muted-soft: "#a3a3a3"
  hairline: "#e2e2e2"
  hairline-strong: "#cfcfcf"
  canvas: "#ffffff"
  surface-soft: "#f7f7f5"
  surface-card: "#fafaf7"
  surface-elevated: "#f0f0ec"
  surface-yellow-band: "#d4c700"
  on-primary: "#0a0a0a"
  on-dark: "#0a0a0a"
  on-yellow: "#0a0a0a"
  accent-emerald: "#1a8a4a"
  accent-emerald-bg: "#e8f5ec"
  accent-rose: "#c0392b"
  accent-rose-bg: "#fbeae8"
  accent-blue: "#1d5fbf"
  accent-blue-bg: "#e8f0fc"
  accent-amber: "#96690a"
  accent-amber-bg: "#faf3dc"
  success: "#1a8a4a"
  warning: "#96690a"
  error: "#c0392b"

typography:
  display-xl:
    fontFamily: "Inter, sans-serif"
    fontSize: 56px
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: -2px
  display-lg:
    fontFamily: "Inter, sans-serif"
    fontSize: 40px
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: -1.5px
  display-md:
    fontFamily: "Inter, sans-serif"
    fontSize: 32px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: -1px
  display-sm:
    fontFamily: "Inter, sans-serif"
    fontSize: 24px
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: -0.3px
  title-lg:
    fontFamily: "Inter, sans-serif"
    fontSize: 20px
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: -0.2px
  title-md:
    fontFamily: "Inter, sans-serif"
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  title-sm:
    fontFamily: "Inter, sans-serif"
    fontSize: 15px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  stat-display:
    fontFamily: "Inter, sans-serif"
    fontSize: 40px
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: -1px
  body-md:
    fontFamily: "Inter, sans-serif"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.55
  body-sm:
    fontFamily: "Inter, sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5
  caption:
    fontFamily: "Inter, sans-serif"
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.4
  caption-uppercase:
    fontFamily: "Inter, sans-serif"
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 1px
  code:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5
  money:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: -0.1px
  money-lg:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.2
  button:
    fontFamily: "Inter, sans-serif"
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1
  nav-link:
    fontFamily: "Inter, sans-serif"
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.4
  table-header:
    fontFamily: "Inter, sans-serif"
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: 0.5px

rounded:
  xs: 4px
  sm: 6px
  md: 8px
  lg: 12px
  pill: 9999px
  full: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  section: 64px

components:
  # ---- carried over from source, inverted ----
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: "12px 20px"
    height: 40px
  button-primary-active:
    backgroundColor: "{colors.primary-active}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
  button-primary-disabled:
    backgroundColor: "{colors.primary-disabled}"
    textColor: "{colors.muted}"
    rounded: "{rounded.md}"
  button-secondary:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: "12px 20px"
    height: 40px
    border: "1px solid {colors.hairline}"
  button-text-link:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.button}"
  button-icon-circular:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.full}"
    size: 32px
    border: "1px solid {colors.hairline}"
  text-link:
    backgroundColor: transparent
    textColor: "{colors.accent-blue}"
    typography: "{typography.body-md}"
  top-nav:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.nav-link}"
    height: 56px
    border: "0 0 1px {colors.hairline} solid"
  feature-card-dark:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    typography: "{typography.title-md}"
    rounded: "{rounded.lg}"
    padding: "{spacing.xl}"
    border: "1px solid {colors.hairline}"
  code-window-card:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.body-strong}"
    typography: "{typography.code}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
    border: "1px solid {colors.hairline-strong}"
  text-input:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: "10px 14px"
    height: 40px
    border: "1px solid {colors.hairline}"
  text-input-focused:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    border: "2px solid {colors.primary-active}"
  category-tab:
    backgroundColor: transparent
    textColor: "{colors.muted}"
    typography: "{typography.nav-link}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
  category-tab-active:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.ink}"
    typography: "{typography.nav-link}"
    rounded: "{rounded.md}"
  badge-pill:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.pill}"
    padding: "4px 12px"
  badge-yellow:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.caption-uppercase}"
    rounded: "{rounded.pill}"
    padding: "4px 12px"
  stat-callout:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.stat-display}"
  footer:
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.muted}"
    typography: "{typography.body-sm}"
    padding: "{spacing.xl}"
    border: "1px solid {colors.hairline}"

  # ---- new: reconciliation-specific ----
  status-badge-matched:
    backgroundColor: "{colors.accent-emerald-bg}"
    textColor: "{colors.accent-emerald}"
    typography: "{typography.caption-uppercase}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  status-badge-exception:
    backgroundColor: "{colors.accent-rose-bg}"
    textColor: "{colors.accent-rose}"
    typography: "{typography.caption-uppercase}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  status-badge-excluded:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.muted}"
    typography: "{typography.caption-uppercase}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  status-badge-review:
    backgroundColor: "{colors.accent-amber-bg}"
    textColor: "{colors.accent-amber}"
    typography: "{typography.caption-uppercase}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  pass-tag-cascade:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.body-strong}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
    border: "1px solid {colors.hairline-strong}"
  pass-tag-llm:
    backgroundColor: "{colors.primary-disabled}"
    textColor: "{colors.body-strong}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
    border: "1px solid {colors.primary}"
  money-cell:
    backgroundColor: transparent
    textColor: "{colors.body-strong}"
    typography: "{typography.money}"
  money-cell-negative:
    backgroundColor: transparent
    textColor: "{colors.accent-rose}"
    typography: "{typography.money}"
  money-total:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.money-lg}"
  data-table:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    border: "1px solid {colors.hairline}"
  data-table-header:
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.muted}"
    typography: "{typography.table-header}"
    padding: "10px 16px"
    border: "0 0 1px {colors.hairline-strong} solid"
  data-table-row:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    padding: "12px 16px"
    border: "0 0 1px {colors.hairline} solid"
  data-table-row-hover:
    backgroundColor: "{colors.surface-soft}"
  data-table-row-selected:
    backgroundColor: "{colors.primary-disabled}"
  proof-table:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
    border: "1px solid {colors.hairline-strong}"
  proof-table-row:
    backgroundColor: transparent
    typography: "{typography.money}"
    padding: "6px 0"
    border: "0 0 1px {colors.hairline} solid"
  proof-table-row-total:
    backgroundColor: "{colors.surface-elevated}"
    typography: "{typography.money-lg}"
    padding: "10px 12px"
    rounded: "{rounded.sm}"
  proof-delta-zero:
    backgroundColor: "{colors.accent-emerald-bg}"
    textColor: "{colors.accent-emerald}"
    typography: "{typography.money}"
    rounded: "{rounded.sm}"
    padding: "4px 10px"
  proof-delta-nonzero:
    backgroundColor: "{colors.accent-rose-bg}"
    textColor: "{colors.accent-rose}"
    typography: "{typography.money}"
    rounded: "{rounded.sm}"
    padding: "4px 10px"
  waterfall-band-positive:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    border: "1px solid {colors.hairline-strong}"
  waterfall-band-negative:
    backgroundColor: "{colors.accent-rose-bg}"
    textColor: "{colors.accent-rose}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    border: "1px solid {colors.accent-rose}"
  waterfall-band-total:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.title-sm}"
    rounded: "{rounded.sm}"
  waterfall-connector:
    backgroundColor: "{colors.hairline-strong}"
  audit-trail-item:
    backgroundColor: transparent
    textColor: "{colors.body}"
    typography: "{typography.body-sm}"
    padding: "8px 0"
    border: "0 0 1px {colors.hairline} solid"
  audit-trail-stage-tag:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.muted}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "2px 6px"
  drawer-panel:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
    border: "1px solid {colors.hairline}"
  drawer-source-card:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
    border: "1px solid {colors.hairline}"
  metric-strip-cell:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    typography: "{typography.stat-display}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
    border: "1px solid {colors.hairline}"
  metric-strip-label:
    backgroundColor: transparent
    textColor: "{colors.muted}"
    typography: "{typography.caption-uppercase}"
  filter-chip:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.pill}"
    padding: "5px 12px"
    border: "1px solid {colors.hairline-strong}"
  filter-chip-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.canvas}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.pill}"
    padding: "5px 12px"
---

## Overview

This is the ClickHouse marketing design language inverted to a white canvas and extended
for a data-dense financial reconciliation dashboard. The posture that made the source
system worth adapting — one scarce accent color, flat bordered surfaces, no shadows, no
gradients, monospace for anything numeric — transfers directly to a screen full of money
and match decisions. What didn't transfer (hero bands, pricing tiers, CTA bands,
customer-logo strips) has been dropped. What was missing (status badges, an arithmetic
proof display, a waterfall, an audit trail) has been added in the same voice.

**The inversion, precisely:** canvas flips from near-black (#0a0a0a) to white (#ffffff);
ink flips from white to near-black (#0a0a0a). The yellow shifts from a screen-native
`#faff69` to a print-safe `#d4c700` — the original hex fails contrast against white at
body-text weight, so it's darkened until it holds on `{colors.canvas}` while still reading
as the same color family. **Yellow's scarcity rule is unchanged and, if anything,
tightened**: on this dashboard it appears on `button-primary` and `badge-yellow` only. It
never appears on a status badge, a money figure, or a table row — those have their own
semantic colors (emerald / rose / amber) so that "yellow" keeps meaning exactly one thing:
primary action.

**Key characteristics carried over:**
- Single accent discipline. One yellow, used scarcely, at full saturation.
- Flat + bordered, never shadowed. Depth comes from `{colors.surface-card}` /
  `{colors.surface-elevated}` tone steps, not elevation.
- Inter at weight 700 for display, 600 for titles/buttons, 400 for body. No serif.
- `{rounded.lg}` (12px) for cards, `{rounded.md}` (8px) for controls, `{rounded.pill}` for
  badges only.

**Key characteristics added for this dashboard:**
- **Money is monospace, always.** `{typography.money}` / `{typography.money-lg}` (JetBrains
  Mono) for every rupee figure, in every screen. Never in the sans body face — an amount
  and a label must never share a typeface at a glance.
- **Status has its own three-color language**, deliberately separate from the yellow
  brand accent: emerald (matched), rose (exception / false match), amber (requires
  review). Excluded records get neutral grey — they are not a status, they are a
  non-event.
- **The origin of a match is always visible.** `pass-tag-cascade` (grey) vs
  `pass-tag-llm` (pale yellow outline) on every matched row, so the "deterministic
  dominates, LLM is a sliver" story is visible without narration, per
  `master_specification.md` §23.3.

## Colors

### Brand & Accent
- **Primary** (`{colors.primary}` — #d4c700): The single brand accent, darkened from the
  source `#faff69` for white-canvas contrast. Reserved for `button-primary` and
  `badge-yellow` only — never a status, never a money figure.
- **Primary Active** (`{colors.primary-active}` — #b8ad00): Pressed state, and doubles as
  the focus-ring color on `text-input-focused`.
- **Primary Disabled** (`{colors.primary-disabled}` — #f0edc0): Disabled buttons, and
  reused as the pale fill behind `pass-tag-llm` and `data-table-row-selected` — the same
  restraint principle as the source: the tint of the brand color, never the color itself,
  carries secondary meaning.

### Surface
- **Canvas** (`{colors.canvas}` — #ffffff): The page floor. Pure white, the direct
  inversion of the source's near-black.
- **Surface Soft** (`{colors.surface-soft}` — #f7f7f5): Table headers, footer, section
  dividers.
- **Surface Card** (`{colors.surface-card}` — #fafaf7): Feature cards, proof tables,
  drawer source cards. One step off white — the same "barely lighter than canvas" subtlety
  the source used in reverse.
- **Surface Elevated** (`{colors.surface-elevated}` — #f0f0ec): Nested surfaces —
  code-window fill, active tab, badge-pill background, waterfall's neutral bands.
- **Hairline** (`{colors.hairline}` — #e2e2e2): Standard 1px border.
- **Hairline Strong** (`{colors.hairline-strong}` — #cfcfcf): Table-header underline,
  proof-table border, active input focus fallback.

### Text
- **Ink** (`{colors.ink}` — #0a0a0a): Headlines, primary values, active nav.
- **Body** (`{colors.body}` — #3a3a3a): Default running text, audit-trail entries.
- **Body Strong** (`{colors.body-strong}` — #1a1a1a): Table cell text, money-cell default.
- **Muted** (`{colors.muted}` — #767676): Captions, table headers, filter-chip inactive
  text, footer.
- **Muted Soft** (`{colors.muted-soft}` — #a3a3a3): Placeholder text, disabled labels.

### Status semantics (new)
Kept strictly separate from the brand yellow so status always reads unambiguously.
- **Emerald** (`{colors.accent-emerald}` #1a8a4a / bg `{colors.accent-emerald-bg}`
  #e8f5ec): Matched, closes, verified.
- **Rose** (`{colors.accent-rose}` #c0392b / bg `{colors.accent-rose-bg}` #fbeae8):
  Exception, false match, delta ≠ 0, negative money.
- **Amber** (`{colors.accent-amber}` #96690a / bg `{colors.accent-amber-bg}` #faf3dc):
  "Requires human review" — distinct from a hard exception; this is the ambiguous-record
  badge per §23.4. Darkened from an earlier #b8860b (Phase 7): on `#faf3dc` the old value
  read as an afterthought next to the rose exception badge, and this badge marks the
  records carrying the project's strongest honesty claim (both candidates named, neither
  picked). #96690a on #faf3dc is ~4.4:1 — still visibly calmer than rose, no longer the
  weakest element on the screen.
- **Blue** (`{colors.accent-blue}` #1d5fbf): Informational text links only — never a
  status.

## Typography

Inter carries the whole system, exactly as in the source — display, body, buttons,
navigation. **JetBrains Mono is added as a second, deliberate voice reserved for one job:
anything that is a number derived from money or arithmetic.** This is the one addition to
the source's "single typeface" principle, and it exists because a reconciliation dashboard
lives or dies on whether a reviewer can tell, at a glance, "is this a label or a value."

| Token | Size | Weight | Face | Use |
|---|---|---|---|---|
| `{typography.display-xl}` | 56px | 700 | Inter | Not typically used — dashboard has no marketing hero |
| `{typography.display-lg}` | 40px | 700 | Inter | Screen title, e.g. "Run Overview" |
| `{typography.display-md}` | 32px | 700 | Inter | Section heads within a screen |
| `{typography.display-sm}` | 24px | 700 | Inter | Card-group titles |
| `{typography.title-lg}` | 20px | 700 | Inter | Card titles, drawer header |
| `{typography.title-md}` | 18px | 600 | Inter | Sub-card titles |
| `{typography.title-sm}` | 15px | 600 | Inter | Table section labels, waterfall-band-total text |
| `{typography.stat-display}` | 40px | 700 | Inter | Metric-strip headline numbers (record counts, %) |
| `{typography.body-md}` | 15px | 400 | Inter | Default running text |
| `{typography.body-sm}` | 13px | 400 | Inter | Table cells, audit trail, captions |
| `{typography.caption}` | 12px | 500 | Inter | Badge labels, filter chips |
| `{typography.caption-uppercase}` | 11px | 600 | Inter | Status-badge text, table-header labels |
| `{typography.code}` | 13px | 400 | JetBrains Mono | Reason codes, record_key, technical strings |
| `{typography.money}` | 14px | 500 | JetBrains Mono | **Every rupee figure in a table cell** |
| `{typography.money-lg}` | 20px | 600 | JetBrains Mono | Headline totals — bank credited, gross orders |
| `{typography.button}` | 14px | 600 | Inter | Button labels |
| `{typography.table-header}` | 11px | 600 | Inter | Data-table column headers |

**Principle: if it's a rupee amount or a `record_key`/`reason_code`, it's JetBrains Mono.
Everything else — every label, every heading, every sentence of exception text — is
Inter.** This single rule is what lets §23.3's Match Explorer hold 400 rows without the
eye losing track of which column is which.

## Layout

### Spacing
Unchanged from source: 4px base unit, tokens `{spacing.xxs}`→`{spacing.section}`. The
source's 96px section rhythm is tightened to `{spacing.section}` = 64px, because a
dashboard's screens are denser and shorter than a marketing page's scroll.

### Grid
- Max content width ~1280px, matching the source.
- Run Overview (§23.1): 4-column metric-strip row, then a 4-column source-card row below.
- Match Explorer (§23.3): full-width `data-table`, filter-chip row above it.
- Record drawer (§23.5): fixed-width panel (~480px) sliding from the right, 2×2 grid of
  `drawer-source-card` above a scrollable `audit-trail-item` list.

### Whitespace
Denser than the source's marketing rhythm — this is a working tool, not a landing page.
Table rows compress to 12px vertical padding; card padding drops to `{spacing.lg}` (24px)
from the source's `{spacing.xl}` (32px).

## Elevation & Depth

Unchanged philosophy: **no shadows, ever.** Depth is tone-stepping between
`{colors.canvas}` → `{colors.surface-card}` → `{colors.surface-elevated}`, exactly as the
source stepped `{colors.canvas}` → `{colors.surface-card}` → `{colors.surface-elevated}` in
the dark direction. A `drawer-panel` sitting over the page gets a `{colors.hairline}`
border, not a shadow — the source's rule that yellow-vs-dark contrast does the elevation
work becomes, here, white-vs-bordered-card contrast doing the same job.

## Shapes

Unchanged from source: `{rounded.md}` (8px) for controls, `{rounded.lg}` (12px) for cards,
`{rounded.pill}` for badges only. New: `{rounded.sm}` (6px) is used more heavily here than
in the source, for `pass-tag-*`, `proof-delta-*`, and `waterfall-band-*` — small inline
chips that are one step down from a full badge-pill.

## Components

### Carried over from the source (inverted, unchanged in structure)
`button-primary` / `-active` / `-disabled`, `button-secondary`, `button-text-link`,
`button-icon-circular`, `text-link`, `top-nav`, `feature-card-dark`, `code-window-card`,
`text-input` / `-focused`, `category-tab` / `-active`, `badge-pill`, `badge-yellow`,
`stat-callout`, `footer`. All structural rules are unchanged from the source spec — only
color values inverted.

### New — status semantics

**`status-badge-matched`** — Emerald pill. Background `{colors.accent-emerald-bg}`, text
`{colors.accent-emerald}`, type `{typography.caption-uppercase}`, `{rounded.pill}`,
padding `3px 10px`. Used on every row in Match Explorer (§23.3) whose `status ==
"matched"`.

**`status-badge-exception`** — Rose pill, same shape. Used on Exception List (§23.4) rows
and any false match.

**`status-badge-excluded`** — Neutral grey pill, same shape. Used for `NOT_A_SETTLEMENT`
records — deliberately the quietest badge in the system, because exclusion is correct
behaviour, not an event worth emphasis.

**`status-badge-review`** — Amber pill. The "Requires human review" badge named explicitly
in §23.4 for `AMBIGUOUS_DUPLICATE` records.

**`pass-tag-cascade`** — Small grey outlined chip carrying the pass name (`exact`,
`aggregate`, `fee_reversal`…). Background `{colors.surface-elevated}`, border
`{colors.hairline-strong}`.

**`pass-tag-llm`** — Same shape, pale-yellow-outlined instead of grey. Background
`{colors.primary-disabled}`, border `{colors.primary}`. **This is the only place yellow's
tint appears outside a primary button** — a deliberate, visible marker that a record was
resolved by the LLM layer, so the sliver is countable at a glance across the whole table.

### New — money and proof display

**`money-cell`** — Every rupee figure in a table row. JetBrains Mono, `{typography.money}`,
right-aligned by convention (not encoded here — a layout rule for the frontend).

**`money-cell-negative`** — Same, in rose, for debits/refunds shown as negative.

**`money-total`** — Headline totals (bank credited, gross orders) at `{typography.money-lg}`.

**`proof-table`** — The `ArithmeticProof` display inside the record drawer (§23.5). Card
surface `{colors.surface-card}`, monospace body, bordered. Renders as a labeled list:
gross, fees, tax, refunds, expected_net, observed_net, delta — each a `proof-table-row`.

**`proof-table-row-total`** — The `expected_net = observed_net` closing line, set apart
with `{colors.surface-elevated}` background and `{typography.money-lg}`.

**`proof-delta-zero`** — Small emerald pill wrapping `delta: 0` — the visual "this closes"
confirmation.

**`proof-delta-nonzero`** — Same shape in rose, for a rejected proposal's proof. This is
the component that carries the `llm-hallucination` failure-injection moment from
§24 — the model's confident proposal, shown next to a rose `delta ≠ 0`, is the single most
important frame in the demo video.

### New — waterfall (Reconciliation Bridge, §23.2)

**`waterfall-band-positive`** — A neutral grey-bordered horizontal bar for an additive
step (e.g. "Prior cycle spillover"). Clickable, filtering Match Explorer per §23.2.

**`waterfall-band-negative`** — Rose-bordered bar for a subtractive step (fees, tax,
refunds, settled-next-cycle).

**`waterfall-band-total`** — The single yellow bar marking the final "Bank credited" line
— **the only waterfall band allowed to use the brand accent**, because it is the one
figure the entire screen exists to prove.

**`waterfall-connector`** — The thin joining line between bands, `{colors.hairline-strong}`.

### New — audit trail & drawer (§23.5)

**`audit-trail-item`** — One row per audit-log entry for a record: stage, action, detail.
Plain list, bottom-hairline separated, no card chrome — this is meant to read like a log,
not a feature list.

**`audit-trail-stage-tag`** — Small grey tag prefixing each entry (`match.exact`,
`verify`, `hypothesize`).

**`drawer-panel`** — The record drawer itself. Bordered, no shadow, `{rounded.lg}`.

**`drawer-source-card`** — One of the four side-by-side source records inside the drawer.
`{colors.surface-card}`, bordered, monospace for any field value, Inter for field labels.

### New — dashboard chrome

**`metric-strip-cell`** — One headline metric on Run Overview (§23.1): match rate,
runtime, unresolved count. Bordered card, `{typography.stat-display}` value, label below
in `metric-strip-label`.

**`filter-chip`** / **`filter-chip-active`** — Match Explorer's per-pass filter row.
Active state inverts to solid ink-on-white, matching the source's `category-tab-active`
logic but as a pill rather than a rectangular tab, since these are toggleable multi-select
filters rather than a single-select nav.

## Do's and Don'ts

### Do
- Reserve `{colors.primary}` for `button-primary`, `badge-yellow`, `pass-tag-llm`'s pale
  outline, and `waterfall-band-total`. Four places. Not five.
- Set every rupee figure in JetBrains Mono via `{typography.money}` or
  `{typography.money-lg}` — no exceptions, no rupee amount in Inter.
- Use the emerald/rose/amber status language consistently across all four screens —
  matched is always emerald, exception is always rose, review is always amber, everywhere.
- Show `pass-tag-cascade` vs `pass-tag-llm` on every matched row so the cascade-dominates
  story is visible without a caption.
- Keep `status-badge-excluded` visually quiet — it should read as "nothing happened here,"
  not as a fourth status competing with the other three.

### Don't
- Don't put yellow on a status badge, a money figure, or a table row background. It has
  exactly one job: mark the primary action or the one total that matters.
- Don't introduce a shadow anywhere. Depth is tone-stepping only, per the source system.
- Don't render a `record_key`, `reason_code`, or amount in Inter — if it's Mono-eligible
  content per the typography table, it must be Mono.
- Don't give `AMBIGUOUS_DUPLICATE` a rose badge. It is amber (`status-badge-review`) —
  distinct from a hard exception, because both candidates are plausible; it's not wrong,
  it's unresolved.
- Don't round `data-table` corners beyond `{rounded.md}` (8px) — dense tabular data reads
  better with restrained radii than with the `{rounded.lg}` used on cards.

## Responsive Behavior

Per `master_specification.md` §23, this is a desktop-first internal tool; no phone
breakpoint is required. Two breakpoints suffice.

| Name | Width | Key changes |
|---|---|---|
| Desktop | ≥ 1024px | Full 4-column metric strip; `data-table` at full column count; drawer slides in at 480px fixed width without reflowing the table |
| Compact | < 1024px | Metric strip 2×2; `data-table` drops secondary columns (pass tag moves into a row-expand); drawer becomes full-width overlay |

Touch targets are not a primary concern (mouse/trackpad tool), but `button-primary` and
`filter-chip` retain the source's 40px / medium targets for consistency.

## Iteration Guide

1. Same discipline as the source: one component at a time, reference by YAML key, never
   inline a hex or a px value that already has a token.
2. New status colors (emerald/rose/amber) are semantic and closed — do not add a fourth
   without updating this file and `master_specification.md` §20.3's reason-code table in
   the same change.
3. Every new component touching money must use `{typography.money}` or `-lg}` — check this
   before merging, the same way `test_money.py` checks the backend.
4. If a new screen element needs emphasis, reach for size/weight in Inter before reaching
   for the yellow. The source's rule holds: bigger before more color.

## Known Gaps

- No dark mode. The source had none either; not needed for a four-day submission.
- Chart-library-free per `master_specification.md` §23.6 — the waterfall must be built as
  bordered `div`/`svg` bands using these tokens, not a charting dependency.
- Animation/transition timings not specified; the source recommended none beyond default
  browser behavior, and a reconciliation tool has no motion requirement beyond the
  drawer's slide-in.