# Dashboard data organization

## Three layers, one read-only dashboard

1. **Source evidence and native warehouse**: existing provider catalogs, source references, checks and append-only inventory history. These remain the collection authority, with original units, currencies, conditions and unknowns.
2. **Public native projections**: `scripts/dashboard_projection.ts` builds searchable provider catalogs, API model/route/flavor summaries and categorized events. It reads warehouse files but does not rewrite them, change source hashes, add aliases, or create comparison quotes.
3. **Reviewed comparisons**: existing model, offering, price and history files remain the calculator's only inputs. Native records are always `comparison_eligible: false`, even when a published amount is structured.

No database or paid storage is required. Vite generates the projections for development and production builds; they are derived assets, not new authoritative history files. The asset allowlist does not publish raw responses, authenticated source archives, credentials, collector scripts or JSONL warehouse logs. Provider metadata is explicitly selected rather than copying entire transport responses.

## Navigation

- **Compare prices** remains the default. Its exact models, USD/token calculations, prompt bands, tiers, cloud regions and observed-price charts are unchanged.
- **Model explorer** separates reviewed canonical models from collected API listings. Each collected row retains its provider and route/flavor context. Equal-looking names do not create canonical aliases. Document labels and cloud SKUs are not counted as API model identities; they are searchable on provider pages.
- **Providers** covers every collected provider group, including gateways and native-unit platforms. Search/filter by source, access type, record kind, billing basis and pricing state. Detail pages retain source-native billing expressions, scope, metadata, provenance and limitations. Records and provider pages have shareable URL parameters.
- **Recent changes** separates reviewed comparison events, native amount changes, billing rules, and catalog discoveries/absences/metadata. Discovery dates are not launch dates. Source absence is not proof of discontinuation.
- **Methodology** documents collection scope, freshness, calculator limitations and exports.

## Lazy assets

The comparison landing page requests no native catalog assets. Native views load a small `catalog/index.json`. `catalog/models.json` loads only for collected model listings. A provider detail file loads only after opening that provider; source history loads only when requested or selecting a record. Each native change category has its own lazy file.

Generated public paths:

- `catalog/index.json`
- `catalog/models.json`
- `catalog/providers/<provider>.json`
- `catalog/history/<provider>.json`
- `catalog/changes/{price,rule,catalog}.json`

Large tables and feeds are paginated. Search and exports operate on all matching records, not just the visible page. The existing global JSON export is explicitly a reviewed-comparison export; native catalogs are exported from provider pages.

## Review and freshness are independent

A current collector does not imply reviewed pricing. Native views show separate pricing, review and freshness labels. Original currencies and decimal amounts are preserved; no automatic FX, DBU/credit/neuron-to-dollar conversion or denominator conversion is performed. Missing or unknown prices do not become zero.

OVHcloud explicitly shows unverified currency. Snowflake PDF page text explicitly remains unreviewed table evidence. Unaligned document cells are shown in source order, not assigned invented column/model relationships. Gateway offers identify commercial access without inventing supplier endpoints.

## Native history classification

Projection generation replays real inventory events in their recorded order. It does not fabricate earlier states or change warehouse history.

A structured native amount change enters the native price feed only when the same record retains the same explicit currency, unit, conditions and source scope. Unit/currency/region/band changes and source-cell extractions go to billing-rule events instead. Unknown units and non-active source expressions cannot imply a price cut. Metadata changes remain catalog events; initial discoveries and first-captured billing guides are labeled as observations.

Native history is an event timeline, not a mixed-unit line chart. Existing reviewed price charts remain in their verified USD/token basis. Linking a native record to an existing reviewed model is allowed only for an exact, same-provider identity already represented by curated offerings; the native rates still do not enter comparisons.

## Validation

Unit tests cover native decimals and units, missing currency/prices, source evidence, same-provider identity links, public projection fields, unsafe URLs, change classification and all real warehouse projections. Browser tests cover lazy loading, provider filters, native deep links, pagination/exports, broad model listings, separate feeds, retry behavior, mobile overflow and WCAG 2.1 AA checks. Existing calculator/history/branding tests remain active.

Dashboard deployment remains separately gated and is not enabled by this presentation change.
