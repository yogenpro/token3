# Collection-first production storage

## Scope and meaning of normalization

The full inventory is independent of dashboard model aliases. It covers every model, meter, SKU dimension and document-table row returned by the 26 selected official source groups, including text/vision, embeddings, reranking, image, video, audio, training, tools and capacity-related billing where present. Public AWS/Azure region scopes are unchanged; adding credentials does not make listings universally exhaustive. Azure now selects the complete East US `Foundry Models` retail service rather than only OpenAI-named products, preserving Azure OpenAI coverage while adding other Azure-metered model families and capacity products. This does not include every Foundry Marketplace offer or the separate Foundry Tools service.

Normalization here means **a common storage schema with stable source-local identities**, not guessed cross-provider equivalence or a universal calculator. `comparison_eligible` is always false in this layer. The dashboard's 216 retained reviewed offerings across 12 billing providers are a separate dataset. Of the 15 expanded source groups, 14 remain inventory-only; Vercel has an explicitly curated gateway token-quote adapter, while every native Vercel record remains comparison-ineligible. New reviewed identities use exact provider/source bindings rather than automatically enrolling a globally recognized alias; see [the expanded source scopes](collection-expansion.md). Gateway/model-provider routes, native credit/DBU/compute billing and unknown currency are not automatically calculator quotes.

Together's reviewed quotes are currently paused by `config/provider_policies.json`. Its free document inventory remains active, without contacting the deposit-gated API even when a local key exists. Retained quotes/history and availability flags stay intact; current calculators/rankings exclude them. Inventory-only checks do not rewrite reviewed files.

DeepSeek validates a complete transposed model table, exact model columns, versions and six peak/off-peak token components before accepting a source. Tool-only/partial pages fail closed. Additional native model records preserve the explicit rates, served version, original context strings, UTC peak schedule and Chinese-public-holiday exception; all original document rows remain. These are not reviewed quotes, aliases, a holiday calendar or inferred currently applicable rates. New records start at their real next collection; no prior change/observation is backfilled.

Records contain:

- `id`, `provider`, `native_id`, `kind`, `label`: native model/meter/SKU identities, or document-local row identities. These are not canonical model aliases.
- `scope`: native region/tier/term/effective-date fields or document headings, tab labels, columns and table scope.
- `billing`: original structured billing rules or quoted document cells. Conditional schedules, multipliers, native billing integers, qualitative prices and formulas remain available without an invented numerical interpretation.
- `rates`: explicit monetary components as decimal strings, currency, source-established unit and conditions. For document expressions, `unit` can be null and `unit_verified` false. Multiple amounts retain their entire quoted expression; a future announced rate is not mislabeled the current rate.
- `metadata`: published modality/context/precision/status fields, or explicit document model strings.

Do not rank unreviewed records by their numerical components: those components may represent a future scheduled price, an example total, or one branch of a formula. No missing value or integer-only billing amount becomes a free USD rate. Distinct provider IDs/regions/serving modes remain separate. Identical repeated source rows can be coalesced; ambiguous differing repeats retain source-local occurrence identities.

## Permanent files

| Path | Policy |
| --- | --- |
| `data/provider_catalogs/<provider>.json` | Full source-native snapshot of current semantic state; rewritten on meaningful changes or a representation/provenance-policy refresh |
| `data/provider_inventory.json` | Catalog pointers/fingerprints, revision counters, latest compact observation provenance, fallback/parser status and archive-reference status |
| `data/inventory_history/manifest.json` | Ordered, checksummed schema-1 warehouse manifest; atomically committed after immutable segments |
| `data/inventory_history/segments/<sha>.jsonl.gz` | Native events and verified compact observations; at most 16 MiB uncompressed per event-boundary segment |
| `data/inventory_history/archive/<sha>.jsonl.gz` | Lossless original migration ledger in bounded segments, with whole-input checksum |
| `data/inventory_history/proofs/<sha>.json` | Two-sided historical request-scope witnesses for narrowly proven retrospective observations |
| `data/collection_checks.jsonl` | Small success/failure ledger per provider/check; retains exact compact Google latest-price observation timestamps/source hashes and distinguishes unchanged checks from outages |
| `data/price_history.csv` | Existing curated observations retained verbatim; future rows only on first observation or actual rate change |
| `data/price_history.json` | Derived mirror for the dashboard |
| `data/latest_prices.json`, `offerings.json`, `status.json` | Freshness/current curated state; updated independently of price history |
| `data/provider_sources/` | Existing legacy source archive, preserved unchanged; no new scheduled raw snapshots |
| `data/historical_evidence/` | Separately authorized retrospective public evidence, native assertions and coverage; offline imports only, with exact-byte sources, bounded immutable segments and an atomic manifest; excluded from public assets |

Source records disappearing from a catalog are `record_no_longer_listed`, **not** proof of a vendor delisting. Only previously reviewed authoritative public catalogs drive the dashboard's absence-based removal policy.

JSON model ordering/object-key formatting and HTML script noise do not change catalog fingerprints. Pricing rules, units, qualifiers, relevant model metadata and billing prose do. A return from price A to B to A creates separate revisions; seeing an old price again is not deduplicated out of history.

History entries are assigned deterministic IDs per provider revision. History is written before advancing the catalog; retrying a partially persisted revision does not append its events twice. Full source normalization failures retain the last good catalog and record an error. A curated parser can fail independently while valid source-native inventory is retained.

Legacy index version lists are migrated to explicit `legacy_source_archive` references. Original observations are never backfilled, discarded or replaced with fixtures. The separately authorized [native history compaction](native-history-compaction.md) changes representation only for proven timestamp-only events, keeps exact original IDs/values/provenance reconstructible, and archives every original byte losslessly. Future native batches append bounded immutable gzip segments before atomically advancing the manifest/catalog; retries deduplicate existing IDs. Legacy JSONL remains compatible for small fixtures, with a 16 MiB write cap rather than unbounded growth. One early schema-1 JSON artifact is parsed-only and cannot be independently rehashed from exact source bytes.

## Google latest-price observations

Google's [Cloud Billing API contract](https://cloud.google.com/billing/docs/reference/rest/v1/services.skus/list#PricingInfo) says that without a requested time range, `pricingInfo.effectiveTime` indicates the latest pricing information within the last 12 hours. It is not, by itself, the date a tariff changed. Repeating a complete SKU record when only this as-of timestamp advances produces substantial false history growth.

The retention exception is deliberately narrow:

- Only Vertex SKU catalogs fetched from the verified HTTPS Cloud Billing endpoint without `startTime`/`endTime` or unknown SKU-query parameters qualify. JSON bodies, dates or model names alone do not establish this contract.
- A record must have exactly one pricing-info object, a valid UTC timestamp, matching native rate timestamps and a matching service/SKU identity. Multiple pricing-info versions, malformed values and other providers/document rows remain semantic.
- Up to 20 minutes after the collection timestamp is allowed because the bounded collection starts before fetching; later future dates remain semantic. Past as-of values retain the verified latest-request interpretation even when older than the advertised 12-hour age. A successful authenticated collection observed this discrepancy, so age is explicitly reported, not used to fabricate tariff changes, erase timestamps or claim fresh billing dates.
- Only `billing.pricing_info[0].effectiveTime` and its matching `rates[].conditions.effective_time` are excluded from this semantic fingerprint. Prices, currencies/FX, units/conversions, tiers, aggregation, regions, metadata, prose, promotions and genuine effective dates remain compared. Raw retained snapshot/event records keep their original fields.

`google_pricing_observation` in the inventory index and successful native check entries stores `default_effective_time`, `record_count`, `older_than_documented_window_count` and an `exceptions` mapping of record ID to every differing timestamp. It never assumes all SKUs share a time. The check's `observed_at`, `source_sha256` and semantic `catalog_sha256` bind that compact metadata to the captured source and retained state. Failed fetches do not copy an old observation into a new check. An independently valid native observation can still be retained when reviewed parsing fails; the failed reviewed check remains explicit.

Verified timestamp-only checks leave the current catalog, semantic revision and inventory history unchanged. Clock aging only updates the compact timing-warning count; it does not create record events, advance the revision or imply a new tariff. Collector fetch/parse health remains independent of this source-time warning. On a genuine change, the full normalized snapshot and changed records are retained as before, including intraday price reverts and source-row absence. Current public provider details reconstruct the exact captured timestamps from the retained state plus the latest compact metadata; observation provenance remains separate from economic changes and native records remain comparison-ineligible.

The first successful collection against an existing schema-1 catalog uses its recorded unbounded request URLs and snapshot time to upgrade the fingerprint/header once. A representation-only upgrade does not advance the semantic revision or `changed_at`, append discoveries/price events, or rewrite old history. That ordinary fingerprint optimization bounds future growth and does not rewrite old history. New change events carry a latest-mode comparison marker only when both snapshots establish that contract; unmarked legacy events keep their prior conservative classification. A distinct, explicitly authorized migration now compacts retrospectively **only** when both historical catalog headers establish the same qualifying request scope and all other canonical record fields are identical. It replaces repeated full bodies with state references and exact timestamps/provenance, preserves original event IDs and a byte-exact original archive, and marks these observations for omission from public tariff/rule feeds. Missing witnesses, schedules, actual changes and uncertainty remain unchanged. See [the migration schema, audit snapshot, recovery and verification commands](native-history-compaction.md).

## Temporary debugging responses

`python -m scripts.collect --response-dir /tmp/pricing-responses` writes gzip public-source collector inputs plus a small provenance manifest. These are not committed. Authenticated Together/Fireworks/Vertex catalog responses are deliberately excluded from public artifacts; configured credential echoes are rejected before persistence.

Hosted collection places responses under `RUNNER_TEMP` and uploads them as Actions artifacts with **7-day retention**. This bounds raw-response storage and avoids permanently growing Git with HTML bundles or reordered API bodies. No R2 bucket, paid database or Git LFS is necessary for launch. Existing legacy files remain because prior observations/data must be preserved. The separately authorized historical evidence ledger is an explicit exception for selected public historical captures; it does not change scheduled collection's temporary-response policy or admit authenticated responses.

## Archive.org references

`--archive-lookups` performs best-effort Availability API lookups only when a public-document catalog changes. It never submits authenticated responses or credentials, and does not require an Internet Archive account. It does not automatically request Save Page Now captures.

A reference is `verified` only if the archived target is exact and its raw replay SHA-256 matches the collector's source body. The archived capture time is stored separately from the observation/check time. A nearest capture with different contents is `content_mismatch`, not proof of the observed prices. Missing captures, service outages or unverifiable redirects are `unavailable` and do not fail collection. API/multi-feed inputs are `not_applicable`.

References are optional provenance, not a claim of guaranteed permanent third-party availability. Retaining change records rather than raw sources trades away the ability to fully reparse every old response; temporary diagnostics and source-native billing expressions mitigate, but do not eliminate, that trade-off.

## GitHub operation

- Repository: public `yogenpro/token3`, default branch `main`.
- Schedule: **06:17 UTC daily**; GitHub schedules are best-effort.
- Manual run: `gh workflow run collect.yml --repo yogenpro/token3 --ref main`.
- Workflow source permissions: read by default; collection job gets `contents: write` to persist data and health.
- Immutable action SHAs, a 20-minute job timeout, local file lock and workflow concurrency protect execution.
- Partial failures retain last-good data, commit error status, then fail the run. Use GitHub Actions notification preferences to receive alerts.
- Active optional repository Actions secrets: `FIREWORKS_API_KEY`, `GOOGLE_CLOUD_BILLING_API_KEY`. Missing keys use explicitly recorded official-document fallbacks. Together is intentionally document-only; no deposit or key is used. Do not put secrets in repository files or `VITE_` build variables.
- Dashboard Pages uses main-only manual releases at the dispatch SHA and a separately gated reusable path after successful strict collection. `ENABLE_PAGES=true`; the user approved `ENABLE_COLLECTION_PUBLISH=true` after verification of PR #2's initial manual release. Automatic releases must be data-only relative to the last published code baseline and use the exact pushed SHA, with full tests/build/browser checks. New code requires explicit manual release; partial collection never auto-publishes. See [publishing](publishing.md).

Original inventory/check files are not copied wholesale into the dashboard. Validated [read-only public native projections](dashboard-data-organization.md) select permitted records, history and observation provenance into schema-2 manifests and SHA-256-addressed chunks capped at 512 KiB uncompressed. Indexes, evidence and observation-batch/event pages load separately; explicit full exports/searches remain complete. This delivery change never rewrites storage/history or promotes native rates. It respects verified observation-only annotations created by the separate authorized warehouse migration, while retaining conservative classification for unmarked legacy events. Reviewed calculators still use their separate curated files. The collection job does not call inference APIs, perform routing, or access negotiated billing-account pricing.

## Historical backfill research

The [historical source map](history-backfill.md) covers discovery options for all 26 indexed groups, including historical-only SKUs. The authorized [historical evidence ledger](historical-evidence-ledger.md) retains selected public evidence across all 26 groups in a separate warehouse, with offline import, exact-byte recovery, native assertions, explicit dates and source-bounded coverage. [The dated expansion report](historical-ledger-expansion.md) records partial retrieval and unresolved lookups; indexed entries are not recovered prices. Manual discovery stages public evidence separately from daily collection. The original ledger remains outside live production history; its authorized read-only historical projection publishes selected fields separately from current catalogs and comparisons. Current collectors must not backdate new observations or treat recovered records as reviewed quotes. The existing preservation and no-fabrication rules remain in force.
