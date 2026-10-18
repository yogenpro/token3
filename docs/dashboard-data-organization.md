# Dashboard data organization

## Three layers, one read-only dashboard

1. **Source evidence and native warehouse**: existing provider catalogs, source references, checks and immutable segmented inventory history, including compact observations and a lossless original migration archive. These remain the collection authority, with original units, currencies, conditions and unknowns.
2. **Public native projections**: `scripts/dashboard_projection.ts` builds searchable provider catalogs, API model/route/flavor summaries and categorized events. It reads warehouse files but does not rewrite them, change source hashes, add aliases, or create comparison quotes.
3. **Reviewed comparisons**: existing model, offering, price and history files remain the calculator's only inputs. Native records are always `comparison_eligible: false`, even when a published amount is structured.

No database or paid storage is required. Vite generates the projections for development and production builds; they are derived assets, not new authoritative history files. The asset allowlist does not publish raw responses, authenticated source archives, credentials, collector scripts or JSONL warehouse logs. Provider metadata is explicitly selected rather than copying entire transport responses.

## Navigation

- **Compare prices** remains the default. USD/token calculations, prompt bands, tiers and regions keep their existing semantics. Billing-source counts distinguish gateways and quote counts; unpublished context fit/account access stay visible. A searchable model picker and six-item local recent-model list fit the expanded catalog. Single-date histories show a compact first-observation snapshot; charts require observations spanning multiple dates. No earlier history is invented. A reviewed digest groups rate-component events by offering/check; one quote update is not three announcements. The expandable workload price map covers all matching reviewed models, chooses the lowest applicable quote per billing source within the selected tier/region scope, exposes that quote's variant/scope, and labels stale, cache-fallback and context-unverified values. Missing cells are unknown/inapplicable, not free; colors compare within a model, never model quality.
- **Model explorer** separates reviewed canonical models from collected API listings. Reviewed models filter by creator/family/billing provider; collected listings filter by source, published modality, billing basis and pricing state. Each collected row retains its provider and route/flavor context. Equal-looking names do not create aliases. Document labels and cloud SKUs are searchable in Providers, not counted as API model identities.
- **Providers** starts with summaries, then compact source indexes. Search covers every indexed identity, scope label, unit/currency and published modality, not full raw JSON or only displayed rows. API model/route, cloud billing dimension and document evidence detail layouts preserve original conditions, source expressions, metadata and provenance. Full expressions are expandable; complete record evidence loads only on selection/export. URLs preserve provider/record identity.
- **Recent changes** separates reviewed events from native amounts, billing rules, and catalog discoveries/absences/metadata. Native views start with observation batches, grouped by provider, exact observed timestamp and category. Opening a batch fetches only chunks intersecting the current event page. Explicit label/provider/event searches examine all selected batches with visible loading/failure states. Discovery dates are not launch dates; source absence is not discontinuation.
- **Coverage** loads only the summary index. Reviewed models/retained and active offers, provider-scoped listings, and mixed native records have different denominators. It shows record kinds, display billing facets, pricing certainty, single-provider/gateway-only comparison depth, unpublished context limits, verified reviewed price events and per-source check status. Counts are derived, never a blanket review percentage or release-date claim.
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

OVHcloud explicitly shows unverified currency. Snowflake PDF page text explicitly remains unreviewed table evidence. Unaligned document cells are shown in source order, not assigned invented column/model relationships. Gateway offers identify commercial access without inventing supplier endpoints.

## Native history classification

Projection generation replays real inventory events in their recorded order. It does not fabricate earlier states or change warehouse history.

A structured native amount change enters the native price feed only when the same record retains the same explicit currency, unit, conditions and source scope. Unit/currency/region/band changes and source-cell extractions go to billing-rule events instead. Unknown units and non-active source expressions cannot imply a price cut. Metadata changes remain catalog events; initial discoveries and first-captured billing guides are labeled as observations.

For new events explicitly verified on both sides as unbounded Google latest-price observations, rolling as-of timestamps are not billing conditions. They do not create a price/rule/catalog event; genuine same-basis tier amounts can be compared without duplicating their structured Money fields as rule changes. Explicit ranges, multi-version schedules and other effective dates retain the conservative rule classification. Unmarked legacy events are not retrospectively reinterpreted or removed. Separately migrated timestamp-only events with persisted two-sided historical request evidence are recognized as observations, not billing-rule changes; their original IDs, values, exact timestamps and provenance remain recoverable from warehouse replay and the original archive. Other native events and current public evidence/record links are unchanged.

Provider detail projections expose whitelisted `pricing_observation` metadata and reconstruct exact current Google timestamps from the retained semantic snapshot plus compact default/exception values. They validate record counts, exception identities, future-time bounds and the older-than-advertised timing-warning count before applying this read-only overlay. The lightweight index does not download the exception map, and projection never rewrites warehouse records, hashes or history. See [observation retention and fingerprint migration](data-collection.md#google-latest-price-observations).

Native history is an event timeline, not a mixed-unit line chart. Existing reviewed price charts remain in their verified USD/token basis. Linking a native record to an existing reviewed model is allowed only for an exact, same-provider identity already represented by curated offerings; the native rates still do not enter comparisons.

## Validation

Cross-language Python/TypeScript tests verify every original migrated event, lossless original archive bytes, historical request witnesses, immutable 16 MiB warehouse segment bounds, retry/commit failures, genuine changes/reversions and unchanged nonqualifying uncertainty. Unit tests cover native amounts/units/unknowns, same-provider identity links, field/URL allowlists, unchanged economic event classification, current Google timestamp reconstruction, all real warehouse projections, separate coverage denominators, immutable UTF-8 chunk bounds/hashes/counts, missing/corrupt/duplicate chunks, oversized records and cross-chunk paging. Browser tests verify a payload-free comparison landing, index-only Coverage, index-before-evidence provider browsing, no automatic history on deep links, batch/event-page downloads, complete filtered exports, full-label history search, retry/no-partial states, directory/recent-model controls, sparse-history snapshots, mobile overflow and WCAG 2.1 AA in both themes. Existing calculator/history/branding tests remain active.

Dashboard publishing stays main-only and gated. Manual code releases use their exact dispatch SHA. A new reusable post-collection path is implemented for review but remains off (`ENABLE_COLLECTION_PUBLISH=false`); after deliberate activation it can publish only successfully collected data-only updates at the exact pushed SHA, never unpublished code/config/docs or failed/partial collection. Both paths test/build before upload. The user chose PR review, not immediate activation; see [publishing boundaries](publishing.md).
