# Token³ interface design system

The user approved the local Interface Design specimen on 2026-11-11: “looks good,
apply and save.” This records the approved appearance for future UI work. It does
not authorize publishing, collection, scope changes, or changes to price eligibility.

## Direction and intent

Token³ is a pricing workbench for a developer comparing the same model across
billing sources for an explicit workload. It should feel precise, calm, and easy
to inspect. The domain is price ledgers, token mixes, billing bases, reviewed
observations, quote conditions, source receipts, and retained history.

Use the existing locally bundled DM Sans for body text and Manrope for headings
and key totals. The approved specimen is the reference; it does not require a new
component library, remote font service, generated image, or additional dependency.

## Visual signature and hierarchy

The signature is a same-model quote ledger. Five concrete expressions are:

1. A model-selection strip ruled above and below, with explicit billing-basis pills.
2. A summary strip in place of four equally prominent boxes; the workload total
   leads through size and weight, separate from per-million-token input/output rates.
3. A surfaced workload editor with inset numeric fields and compact presets.
4. Aligned, tabular quote amounts and relative-cost bars within a scrollable table.
5. A labeled lowest-estimate row, visible scope/fit uncertainty, and source links
   that keep the estimate inspectable.

The provider table is the main working surface. Reduce promotional chrome and
decorative icon tiles before reducing text size or hiding evidence. Retain the
existing semantic document and keyboard order; do not reorder controls with CSS.

## Palette and tokens

The palette comes from paper ledgers, graphite annotations, indigo selection ink,
green verified-estimate marks, and amber unresolved-scope flags.

| Primitive | Light | Dark | Role |
| --- | --- | --- | --- |
| `--ledger-paper` | `#f5f6f4` | `#161d1c` | Page and navigation canvas |
| `--ledger-sheet` | `#ffffff` | `#1c2523` | Working surfaces |
| `--ledger-ink` | `#222c2b` | `#e6eeea` | Primary text |
| `--ledger-pencil` | `#596663` | `#aab9b1` | Supporting text and metadata |
| `--ledger-rule` | `#dde3df` | `#35433d` | Quiet structural rules |
| `--ledger-selection` | `#3e50b4` | `#abb9ff` | Actions, selection, keyboard focus |
| `--ledger-selection-wash` | `#e9edfc` | `#2b3555` | Selected-control background |
| `--ledger-verified` | `#126447` | `#89d5b2` | Existing lowest eligible estimate |
| `--ledger-verified-wash` | `#eaf4ee` | `#243d30` | Lowest-estimate row |
| `--ledger-caution` | `#85551a` | `#e5b778` | Uncertainty and source warnings |

The workbench maps these primitives to the existing semantic variables (`--bg`,
`--surface`, `--text`, `--muted`, `--border`, `--blue`, `--green`, and companions).
Controls use `--control-bg`, `--control-border`, and `--control-focus`. Keep provider
identity colors distinct from selection, price eligibility, and source health.
Quote-table provider marks use an opaque surface in both themes for readable
identity text, including when the containing row is highlighted.

## Depth, typography, and density

Depth comes from quiet rules and small surface-color shifts. Navigation shares the
page canvas; editor/table surfaces sit above it, and inputs are inset. The
workbench adds no card shadows or decorative gradients.

- Spacing base: 4px; usual component padding 16–20px, section separation 24px.
- Type steps: 12px metadata, 14px controls/provider names/prices, 16px body and
  numeric inputs, 20px section headings, 24px working title and secondary totals.
  The hierarchy uses approximately 1.2 steps together with weight and contrast.
- Workload total: 34px/600 on desktop, 30px on mobile. Preserve exact amounts and
  long-value wrapping; do not abbreviate the economic value to fit.
- Core working controls: 4px radius; workload and comparison panels: 6px radius.
  Preserve specialized existing components until they are deliberately restyled.
- Sidebar: 216px on desktop. Content gutters: 32px, 48px from 1500px wide,
  24px at medium widths, and 16px on phones.

## Reusable patterns

- Navigation item: minimum 40px high, 10px/12px padding, 14px text, 4px radius.
  A selected desktop item has a 2px indigo inset rule and sheet background.
  Below 820px the existing navigation scrolls horizontally with a bottom rule.
- Summary: four columns with quiet vertical separators on desktop, two columns
  on phones; no per-metric box. Workload amount is the focal figure.
- Numeric field: 44px high, 12px horizontal padding (8px on phones), 16px tabular
  text, inset fill, and visible focus treatment.
- Table filter: minimum 40px high, 14px text, 4px radius, inset fill. Keep native
  controls and their existing labels and keyboard behavior.
- Model/billing strip: 20px vertical padding on desktop, 16px on phones; billing
  pills remain visible on mobile and wrap without collapsing currencies/credits.
- Quote table: 1060px minimum internal width, 12px metadata headers, 14px provider
  names/prices, 16px vertical row padding. Overflow belongs to the table container,
  never the page. Expanded evidence and export still cover complete data.
- Keyboard focus: 3px selection-color outline with 3px offset; preserve the
  existing input focus treatment, reduced-motion handling, and accessible states.

## Implementation and verification

`dashboard/src/styles.css` supplies shared structure and existing component styles.
`dashboard/src/workbench.css`, imported after it in `main.tsx`, supplies the approved
appearance and visual tokens. Update the appearance there rather than adding
inline one-off colors or a runtime preview flag. Preserve existing native controls
and React behavior; do not port the preview server or its injection code into the app.

Check desktop/mobile and both themes, including populated/empty comparisons,
long identifiers, billing-basis switching, source details, downloads, keyboard
focus, collector warnings, and the other views that share tokens. Keep WCAG 2.1 AA
assertions and viewport-overflow checks. Never hide scope uncertainty, treat
missing prices as free, combine billing bases, or confuse a build with a fresh
observation to simplify the layout.
