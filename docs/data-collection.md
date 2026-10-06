# Collection-first production storage

## Scope and meaning of normalization

The full inventory is independent of dashboard model aliases. It covers every model, meter, SKU dimension and document-table row returned by the 11 selected official sources, including text/vision, embeddings, reranking, image, video, audio, training, tools and capacity-related billing where present. Public AWS/Azure region scopes are unchanged; adding credentials does not make listings universally exhaustive. Azure now selects the complete East US `Foundry Models` retail service rather than only OpenAI-named products, preserving Azure OpenAI coverage while adding other Azure-metered model families and capacity products. This does not include every Foundry Marketplace offer or the separate Foundry Tools service.

Normalization here means **a common storage schema with stable source-local identities**, not guessed cross-provider equivalence or a universal calculator. `comparison_eligible` is always false in this layer. The existing dashboard's 71 reviewed offerings are a separate dataset.

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
| `data/provider_catalogs/<provider>.json` | Current full source-native catalog; rewritten only when semantic content changes |
| `data/provider_inventory.json` | Catalog pointers/fingerprints, revision counters, provenance, fallback/parser status and archive-reference status |
| `data/inventory_history.jsonl` | Initial record discoveries, then changed records, source-row absence and billing-note changes only |
| `data/collection_checks.jsonl` | Small success/failure ledger per provider/check; distinguishes verified unchanged checks from outages |
| `data/price_history.csv` | Existing curated observations retained verbatim; future rows only on first observation or actual rate change |
| `data/price_history.json` | Derived mirror for the dashboard |
| `data/latest_prices.json`, `offerings.json`, `status.json` | Freshness/current curated state; updated independently of price history |
| `data/provider_sources/` | Existing legacy source archive, preserved unchanged; no new scheduled raw snapshots |

Source records disappearing from a catalog are `record_no_longer_listed`, **not** proof of a vendor delisting. Only previously reviewed authoritative public catalogs drive the dashboard's absence-based removal policy.

JSON model ordering/object-key formatting and HTML script noise do not change catalog fingerprints. Pricing rules, units, qualifiers, relevant model metadata and billing prose do. A return from price A to B to A creates separate revisions; seeing an old price again is not deduplicated out of history.

History entries are assigned deterministic IDs per provider revision. History is written before advancing the catalog; retrying a partially persisted revision does not append its events twice. Full source normalization failures retain the last good catalog and record an error. A curated parser can fail independently while valid source-native inventory is retained.

Legacy index version lists are migrated to explicit `legacy_source_archive` references. Original historical rows are never backfilled, sparsified or replaced with fixtures. One early schema-1 JSON artifact is parsed-only and cannot be independently rehashed from exact source bytes.

## Temporary debugging responses

`python -m scripts.collect --response-dir /tmp/pricing-responses` writes gzip public-source collector inputs plus a small provenance manifest. These are not committed. Authenticated Together/Fireworks/Vertex catalog responses are deliberately excluded from public artifacts; configured credential echoes are rejected before persistence.

Hosted collection places responses under `RUNNER_TEMP` and uploads them as Actions artifacts with **7-day retention**. This bounds raw-response storage and avoids permanently growing Git with HTML bundles or reordered API bodies. No R2 bucket, paid database or Git LFS is necessary for launch. Existing legacy files remain only because prior observations/data must be preserved.

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
- Optional repository Actions secrets: `TOGETHER_API_KEY`, `FIREWORKS_API_KEY`, `GOOGLE_CLOUD_BILLING_API_KEY`. Missing keys use explicitly recorded official-document fallbacks. Do not put secrets in repository files or `VITE_` build variables.
- Dashboard Pages deployment is off. It requires separate Pages setup, `ENABLE_PAGES=true`, and manual dispatch of `deploy.yml`.

Inventory/check files are intentionally excluded from the dashboard build until their curation/display is designed. The collection job does not call inference APIs, perform routing, or access negotiated billing-account pricing.
