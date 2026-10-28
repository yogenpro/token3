# Dashboard data organization

## Three layers, one read-only dashboard

1. **Source evidence and native warehouse**: existing provider catalogs, source references, checks and immutable segmented inventory history, including compact observations and a lossless original migration archive. These remain the collection authority, with original units, currencies, conditions and unknowns.
2. **Public native projections**: `scripts/dashboard_projection.ts` builds searchable provider catalogs, API model/route/flavor summaries and categorized events. It reads warehouse files but does not rewrite them, change source hashes, add aliases, or create comparison quotes.
3. **Reviewed comparisons**: existing model, offering, price and history files remain the calculator's only inputs. Native records are always `comparison_eligible: false`, even when a published amount is structured.

No database or paid storage is required. Vite generates the projections for development and production builds; they are derived assets, not new authoritative history files. The asset allowlist does not publish raw responses, authenticated source archives, credentials, collector scripts or JSONL warehouse logs. Provider metadata is explicitly selected rather than copying entire transport responses.

The separate [historical evidence ledger](historical-evidence-ledger.md) belongs to the warehouse layer. The authorized Historical evidence view reads it through a dedicated whitelisted projection, described below. Its original source assets, manifest and segments are never copied into public assets. Retrospective assertions do not enter current model listings, reviewed exports or price charts.

## Navigation

- **Compare prices** remains the default. Calculations isolate USD, EUR, Databricks DBUs and Snowflake AI Credits; there is no assumed FX or credit conversion. Prompt bands, tiers and regions keep their existing semantics. DeepSeek uses an explicitly selected peak/off-peak scenario, default peak; both controls have shareable URL parameters. Billing-source counts distinguish gateways and quote counts; unpublished context fit/account access stay visible. A searchable model picker and six-item local recent-model list fit the expanded catalog. Single-date histories show a compact first-observation snapshot; charts require observations spanning multiple dates. No earlier history is invented. A reviewed digest groups rate-component events by offering/check; one quote update is not three announcements. The expandable workload price map covers all matching reviewed models, chooses the lowest applicable quote per billing source within the selected tier/region scope, exposes that quote's variant/scope, and labels stale, cache-fallback and context-unverified values. Missing cells are unknown/inapplicable, not free; colors compare within a model, never model quality.
- **Model explorer** separates reviewed canonical models from collected API listings. Reviewed models filter by creator/family/billing provider; collected listings filter by source, published modality, billing basis and pricing state. Each collected row retains its provider and route/flavor context. Equal-looking names do not create aliases. Document labels and cloud SKUs are searchable in Providers, not counted as API model identities.
- **Providers** starts with summaries, then compact source indexes. Search covers every indexed identity, scope label, unit/currency and published modality, not full raw JSON or only displayed rows. API model/route, cloud billing dimension and document evidence detail layouts preserve original conditions, source expressions, metadata and provenance. Full expressions are expandable; complete record evidence loads only on selection/export. URLs preserve provider/record identity.
- **Recent changes** separates reviewed events from native amounts, billing rules, and catalog discoveries/absences/metadata. Native views start with observation batches, grouped by provider, exact observed timestamp and category. Opening a batch fetches only chunks intersecting the current event page. Explicit label/provider/event searches examine all selected batches with visible loading/failure states. Discovery dates are not launch dates; source absence is not discontinuation.
- **Coverage** loads only the summary index. Reviewed models/retained and active offers, provider-scoped listings, and mixed native records have different denominators. It shows record kinds, display billing facets, pricing certainty, single-provider/gateway-only comparison depth, unpublished context limits, verified reviewed price events and per-source check status. Counts are derived, never a blanket review percentage or release-date claim.
- **Historical evidence** has its own summary-only provider overview, provider-scoped search indexes and on-demand historical expressions. Capture/lookup states, original scopes, dates and correction references remain separate from current collector health and reviewed prices. Provider/assertion deep links use `view=historical&provider=...&record=...`.
- **Methodology** documents collection scope, freshness, calculator limitations and exports.

Together comparisons are intentionally paused by the shared `config/provider_policies.json` operating policy. Current rankings, model directory prices, comparison CSVs and workload-map cells exclude its quotes; retained active flags, reviewed baseline and historical timelines are not rewritten. Coverage/provider pages label the pause separately from collector health and vendor availability. JSON reviewed exports include the pause policy.

Every view labels the included collection timestamp separately from build time using the small generated `publication.json`. It binds to `status.json`; mismatched snapshots fail loading. A build is not a new source observation or an asserted deployment timestamp. No browser GitHub/provider fetch is introduced; see [publication provenance](publishing.md#freshness-metadata).

## Lazy assets

The comparison landing page requests no native assets. Native views load a small `catalog/index.json` (schema 2). Coverage needs no catalog payloads. Models, provider details and history use schema-2 manifests, referencing content-addressed schema-1 chunks; these versions describe public delivery, not a warehouse migration.

Generated public paths:

- `catalog/index.json`: provider scope/provenance and independently labeled coverage summaries.
- `catalog/models.json`: manifest for complete provider-scoped listing indexes.
- `catalog/providers/<provider>.json`: source notes/provenance, record count, index-chunk and full-evidence-chunk references.
- `catalog/history/<provider>.json`: exact provider observation batches/counts and event-chunk references.
- `catalog/changes/{price,rule,catalog}.json`: corresponding category observation-batch manifests.
- `catalog/chunks/<sha256>.json`: immutable index, evidence, listing or event envelopes, each at most **512 KiB uncompressed**.

Each reference binds a safe same-origin path, exact SHA-256, UTF-8 byte length and row count. Browser verification requires Web Crypto on HTTPS or localhost; insecure LAN HTTP receives an explicit error, never a verification bypass. Manifests validate completeness; browser loads check bytes, hashes, schemas, counts and duplicate identities before exposing results. At most four chunk requests run concurrently, with per-request timeouts and cancellation of stale searches/selections. Oversized atomic records fail projection explicitly rather than truncating source evidence. Chunk failures remain recoverable errors, never apparent empty/short successful catalogs.

Provider indexes contain exact source-local identities, display scope/billing/pricing facets, currencies/units, published modalities, at most two amount/unit previews (not complete conditions), and evidence pointers. Filtering/search examines the complete index. Full billing/metadata is not duplicated into search payloads; it remains accessible in selected evidence and filtered native exports. Those exports fetch every required evidence chunk and retain every matching record, not just the visible page; failed exports emit no partial file.

Provider history is opt-in, including on a record deep link. Batch paging fetches only intersecting event chunks. Explicit full-history searches and selected-record history searches may fetch many bounded chunks; they show progress and return complete matching results only after all required chunks validate. Category/provider manifests share identical event chunks rather than duplicating whole histories. Public chunking does not discard retained events or reclassify history to improve delivery sizes. The distinct, authorized [warehouse compaction](native-history-compaction.md) provides explicitly verified observation-only annotations; original events remain reconstructible and archived. Public batches contain change-bearing observations, not every unchanged daily check or compact as-of observation.

The global JSON export remains reviewed-comparison data; native records export separately from provider pages. No warehouse file, reviewed history row, source hash or quote permission is changed by this delivery layer.

## Review and freshness are independent

A current collector does not imply reviewed pricing. Native views show separate pricing, review and freshness labels. Original currencies and decimal amounts are preserved; no automatic FX, DBU/credit/neuron-to-dollar conversion or denominator conversion is performed. Missing or unknown prices do not become zero.

OVHcloud native API records explicitly show unverified currency; separate reviewed website price cards establish EUR for selected quotes. Original Snowflake PDF page records remain comparison-ineligible; the independent quote adapter validates selected aligned Table 6(b) rows in AI Credits. Unaligned document cells are shown in source order, not assigned invented column/model relationships. Gateway offers identify commercial access without inventing supplier endpoints.

## Historical public projection

`scripts/historical_projection.py` first verifies the entire ledger, including exact
source hashes, archive/index witnesses and reproducible extraction. It emits only
explicitly selected capture provenance, assertion identity/scope/expressions,
lookup states and append-only corrections. Model metadata uses a field allowlist;
arbitrary responses/transport receipts, disk paths, raw bodies and credentials are
excluded. Nested credential fields or credential-bearing selected URLs fail the
projection. AWS decimals/units, native pricing objects, unknowns, document cells,
scope conditions and unaligned PDF text preserve their source meanings. This
projection grants no quote review or alias permission.

Historical OVHcloud catalogs also preserve the explicitly selected
`metadata.usage_information` pricing, rate-limit and status fields. Other metadata,
inference endpoints and performance measurements are excluded. Nested native
amounts retain their original units and unknown currency; their presence grants
no retrospective comparison permission.

`buildHistoricalAssets` in `scripts/dashboard_projection.ts` runs that offline
verification with `python3` from `PATH`, then validates the public schemas in
`dashboard/src/lib/historical.ts`. Vite publishes:

- `catalog/historical/index.json`: small schema-2 overview, ledger snapshot hash,
  provider names, separately counted captures/assertions/lookup checks, retained
  archive spans and interpretation-state totals.
- `catalog/historical/<provider>.json`: schema-2 manifest, selected capture
  provenance, corrections and exact index/evidence/check chunk references.
- `catalog/chunks/<sha256>.json`: schema-1 historical index, evidence or lookup
  envelopes, sharing the existing 512 KiB byte/hash/count validation and bounded
  concurrency. These are projections, not warehouse JSONL or raw source files.

Historical chunks may wrap their original schema-1 JSON in a versioned
`gzip-base64-v1` JSON envelope when it reduces wire size. The existing `.json`
path and manifest SHA-256/byte count bind the complete encoded envelope. It adds
the original uncompressed byte count and SHA-256; both wire and decoded data are
capped at 512 KiB. The browser checks the wire hash, validates the envelope,
streams bounded gzip decoding, checks the decoded hash/bytes, then validates all
original record schemas/counts. Plain chunks remain supported. Bad gzip, altered
decoded hashes, oversized expansion and incomplete records fail visibly without
partial catalogs or exports. Compression preserves every selected field and ID;
it does not publish raw warehouse/source archives. Build verification and privacy
tests inspect decoded fields as well as the encoded asset bytes.

This avoids growing the static artifact beyond
[GitHub Pages' published-site limit](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
as historical evidence expands. It adds no backend, paid storage or dependency;
the build uses Node's gzip codec and the browser uses `DecompressionStream`.
The production build rejects an emitted site above 1,000,000,000 bytes; it never
trims evidence or exports to fit the limit. Publishing still requires its existing
code-release authorization and exact-SHA gates.

The comparison landing and Coverage never request historical assets. The historical
overview downloads its summary only; choosing a provider loads its complete compact
assertion index. Search covers every indexed native ID, label and identity scope,
not raw response bodies or just a visible page. Type/capture/date filters preserve
ledger order; archive, publication, retrieval and reported-effective date bases
are explicit. Unknown dates are excluded only by an active date bound. A selected
assertion loads only its evidence chunk and shows all date meanings separately.
Captures with zero assertions remain inspectable. Lookup checks load only on request.

Historical exports load every matching evidence chunk with progress/cancellation,
validate selected identities and include capture provenance and relevant correction
references. Errors produce no partial file. Historical JSON remains separate from
native current catalogs and reviewed comparison exports. No common-denominator
prices, inferred tariff intervals, retirement claims or historical line charts
are generated. A Snowflake document dated 2021 does not date later AI SKUs to 2021.

Development/builds require the existing Python requirements even without running
collectors. Development verifies/projects before serving, rather than making the
first browser request wait on reconstruction. The expanded archive corpus uses a
private record-at-a-time build bridge rather than one enormous stdout JSON string;
each bridge record is capped at 1 MiB and complete counts/schemas are checked.
The bridge is deleted after use and never published. Public JSON chunks retain
their existing 512 KiB cap, hash checks and complete index/evidence validation.
The verifier has a 15-minute bound; Playwright/server and full-corpus test setup
allow 20 minutes including schema/chunk validation. Vitest's
internal server does not redundantly prepare browser assets before its dedicated
full-corpus projection test. Published visitors still fetch only static files. The source manifest
mtime participates in development cache invalidation; projection never mutates it.
The full index/evidence binding test has its own three-minute bound while retaining
all assertions. CI and Pages build jobs allow 45 minutes for complete tests,
production builds, browser startup and accessibility checks. These resource bounds
do not change release gates, permissions or source/economic validation.

The full-corpus warehouse-byte/privacy check has a bounded 60-second allowance for
hashing every source and inspecting every decoded public chunk. Its assertions
are unchanged; the decoded privacy inspection remains complete after compression.

Local validation for this historical release on 2026-10-26 passed 102 frontend
tests, 297 Python tests, TypeScript, the production build and all 52 Playwright
tests, including both themes, mobile layout, complete exports and corrupt-chunk
recovery. Projection left every historical warehouse byte unchanged. These local
results are separate from hosted CI and deployment verification.

## Native history classification

Projection generation replays real inventory events in their recorded order. It does not fabricate earlier states or change warehouse history.

A structured native amount change enters the native price feed only when the same record retains the same explicit currency, unit, conditions and source scope. Unit/currency/region/band changes and source-cell extractions go to billing-rule events instead. Unknown units and non-active source expressions cannot imply a price cut. Metadata changes remain catalog events; initial discoveries and first-captured billing guides are labeled as observations.

For new events explicitly verified on both sides as unbounded Google latest-price observations, rolling as-of timestamps are not billing conditions. They do not create a price/rule/catalog event; genuine same-basis tier amounts can be compared without duplicating their structured Money fields as rule changes. Explicit ranges, multi-version schedules and other effective dates retain the conservative rule classification. Unmarked legacy events are not retrospectively reinterpreted or removed. Separately migrated timestamp-only events with persisted two-sided historical request evidence are recognized as observations, not billing-rule changes; their original IDs, values, exact timestamps and provenance remain recoverable from warehouse replay and the original archive. Other native events and current public evidence/record links are unchanged.

Provider detail projections expose whitelisted `pricing_observation` metadata and reconstruct exact current Google timestamps from the retained semantic snapshot plus compact default/exception values. They validate record counts, exception identities, future-time bounds and the older-than-advertised timing-warning count before applying this read-only overlay. The lightweight index does not download the exception map, and projection never rewrites warehouse records, hashes or history. See [observation retention and fingerprint migration](data-collection.md#google-latest-price-observations).

Native history is an event timeline, not a mixed-unit line chart. Reviewed price charts are filtered to one explicitly selected USD/EUR/DBU/AI Credit per-token basis and DeepSeek scenario; mixed bases cannot form a chart. Linking a native record to an existing reviewed model is allowed only for an exact, same-provider identity already represented by curated offerings; the native rates still do not enter comparisons.

## Validation

Cross-language Python/TypeScript tests verify every original migrated event, lossless original archive bytes, historical request witnesses, immutable 16 MiB warehouse segment bounds, retry/commit failures, genuine changes/reversions and unchanged nonqualifying uncertainty. Unit tests cover native amounts/units/unknowns, same-provider identity links, field/URL allowlists, unchanged economic event classification, current Google timestamp reconstruction, all real warehouse projections, separate coverage denominators, immutable UTF-8 chunk bounds/hashes/counts, missing/corrupt/duplicate chunks, oversized records and cross-chunk paging. Browser tests verify a payload-free comparison landing, index-only Coverage, index-before-evidence provider browsing, no automatic history on deep links, batch/event-page downloads, complete filtered exports, full-label history search, retry/no-partial states, directory/recent-model controls, sparse-history snapshots, mobile overflow and WCAG 2.1 AA in both themes. Existing calculator/history/branding tests remain active.

Dashboard publishing stays main-only and gated. Manual code releases use their exact dispatch SHA. The user approved PR #2's merge and initial manual release, followed by `ENABLE_COLLECTION_PUBLISH=true` only after release verification. This reusable post-collection path can publish only successfully collected data-only updates at the exact pushed SHA, never unpublished code/config/docs or failed/partial collection. Both paths test/build before upload. The authorization is data-only, not standing permission for new code releases; see [publishing boundaries](publishing.md).
