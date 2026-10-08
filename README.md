# TokenTokenToken (Token³)

Stylized as **Token³** (Token cubed), inspired by CamelCamelCamel.

**Same model. Different price.** A small, transparent LLM inference pricing dashboard built from the [original MVP plan](docs/mvp-plan.md).

No backend, SQL database, routing, or model inference calls. React + TypeScript + Vite render a static dataset; Python observes official provider APIs and pricing documents. Optional collector-only API keys enable additional structured sources; visitors need no keys. GitHub Actions can collect daily and deploy to GitHub Pages.

## Run locally

Requires Node.js 22.12+ (Node 24 recommended), Python 3.9+ (3.12 recommended), and npm.

```bash
npm ci
npm run dev
```

Open **http://localhost:5173**. Real observations are included, so no collection or Python setup is needed just to view the dashboard.

To refresh official prices:

```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m scripts.collect --strict
```

`npm run collect` uses `python3` from your current environment. Collection spans 26 providers; complete pagination, large documents and network retries can take several minutes. The dashboard’s Refresh button reloads the **published files**, not live provider sources.

### API-first collection

DeepInfra, Novita, Azure and AWS already use structured APIs/price feeds without keys. Together AI and Fireworks now prefer their pricing/catalog APIs when `TOGETHER_API_KEY` and `FIREWORKS_API_KEY` are set. Vertex adds a complete public USD Cloud Billing SKU catalog when `GOOGLE_CLOUD_BILLING_API_KEY` is set; its reviewed dashboard quotes still use the pricing document until SKU-to-offering mapping is curated. Enable the Cloud Billing API and restrict that key to it. This does not access negotiated billing-account prices.

```bash
cp .env.example .env
# Edit .env locally with optional credentials; it is gitignored.
set -a
source .env
set +a
python -m scripts.collect --strict
```

Python does **not** load `.env` automatically. Set the same three names as GitHub repository Actions secrets for hosted collection; the workflow passes them only to the collection step. Never use `VITE_` variables for secrets: those are bundled into the public app.

If a key is missing or an API request fails, collection uses the official document and records the reason in `status.json` and `provider_inventory.json` (`source_kind`, `fallback_reason`), as well as the CLI output. A successfully fetched API response with incompatible curated pricing is never silently replaced with guessed prices. Its last good curated prices remain; independently valid full-inventory records can still be retained. New public raw responses are transient diagnostics, not permanent Git snapshots. API requests use headers, never keys in archived URLs; authenticated redirects are rejected. No inference endpoint is called.

OpenAI, Anthropic, Gemini Developer API and Groq's documented model-list responses do not expose list-price fields. Their official pricing documents remain necessary; model availability APIs and account usage/cost APIs are not substitutes for public price catalogs. See [the source/API capability review](docs/pricing-sources.md).

## What’s built

- Model selector and watchlist for 12 manually curated canonical models, including proprietary OpenAI, Anthropic, and Google releases.
- Current input/output/cache read/cache write comparisons with precision, context, variant, service tier, and region.
- Per-request, total-workload, and per-million-request cost calculations. Set requests to `1,000,000` for that total.
- Cheapest estimate for your actual input/output/cache mix; inapplicable prompt-price bands and known context/output limits cannot win.
- Standard/priority/flex/all-tier filters, sortable prices and estimates, expandable provenance, and comparison CSV export.
- Input/output/cache-read history with stepped lines, date ranges, provider toggles, and an exact-observations table.
- Separate reviewed-price, native-amount, billing-rule, and catalog change feeds; source absence never implies discontinuation.
- Provider-native exploration across all 26 groups: search/filter, original billing rules/units, source scope, provenance, record details, lazy history, and filtered JSON exports.
- A broader provider-scoped API model/route/flavor directory, separate from reviewed canonical models. Collected listing counts are not unique-model counts.
- Collector health, calculation methodology, reviewed dataset downloads, and independent pricing/review/freshness labels.
- Responsive layout, dark theme, keyboard controls, and shareable URLs containing model, tier, view, workload, provider, native record, directory, and feed.
- Readable typography inspired by OpenRouter’s benchmarks page: 16px body text, 14px secondary text/controls, 12px metadata, and 20px section headings. Mobile layouts reflow instead of shrinking text.
- Daily collection, static Pages deployment, and automated unit/collector/browser checks.

### Current coverage

| Canonical model | Providers with observed public prices |
| --- | --- |
| GPT-OSS 120B | DeepInfra, Novita, Together AI, Fireworks, Groq, Amazon Bedrock |
| GPT-OSS 20B | DeepInfra, Novita, Groq, Amazon Bedrock |
| Llama 3.3 70B Instruct | DeepInfra, Novita, Together AI |
| Llama 3.1 8B Instruct | DeepInfra, Novita |
| Qwen3 235B A22B Instruct 2507 | DeepInfra, Novita |
| GPT-5.4 (2026-03-05) | OpenAI API, Microsoft Foundry (Azure OpenAI) |
| GPT-5.4 mini (2026-03-17) | OpenAI API, Microsoft Foundry (Azure OpenAI) |
| Claude Sonnet 4.6 | Anthropic API, Google Vertex AI, Amazon Bedrock |
| Claude Opus 4.6 | Anthropic API, Google Vertex AI, Amazon Bedrock |
| Claude Haiku 4.5 (2025-10-01) | Anthropic API, Google Vertex AI, Amazon Bedrock |
| Gemini 3.8 Flash | Google Gemini API, Google Vertex AI |
| Gemini 3.5 Flash-Lite | Google Gemini API, Google Vertex AI |

The reviewed comparison catalog has **71 offerings across 11 providers**. Claude 4.6 releases are labeled legacy, as in Anthropic's model references: they are included for their verifiable cross-cloud coverage, not presented as the newest Claude versions. Proprietary GPT models are compared with Azure; they are not falsely listed on Bedrock or Vertex. Cloud regions, billing locations, tiers, and prompt-length pricing bands remain explicit.

The original successful run recorded **26 offerings across five providers**, and its historical CSV rows are preserved. Coverage and prices will change. These are first-seen observations, **not** provider launch announcements. No historical prices were fabricated: charts start at the first real collection and become more useful over time.

### Full source-native inventory (separate from comparisons)

Collection now covers **26 providers**, including 15 new **inventory-only** sources: OpenRouter, Vercel AI Gateway, Alibaba Cloud Model Studio, Hugging Face Inference, Snowflake Cortex, Cloudflare Workers AI, Databricks, Oracle Cloud Generative AI, Nebius Token Factory, xAI, Z.ai, OVHcloud, Scaleway, MiniMax and DeepSeek. They do not automatically add dashboard quotes. Gateway routes, credits, DBUs, neurons, native currencies and unpriced offers remain explicit. See [source scopes and collection caveats](docs/collection-expansion.md). No additional credentials are required for these selected public sources.

`data/provider_catalogs/<provider>.json` stores the complete selected catalog as a common source-native record schema: model IDs, meters, SKU dimensions, document rows, native billing rules/expressions, currency, units, regions, tiers, effective dates and relevant metadata. No dashboard alias filter is applied. Numerical monetary amounts are decimal strings; units are only attached when the source establishes them. Complex formulas, conditional schedules, native billing integers, ambiguous units and qualitative prices remain explicit—not guessed into USD/token rates. Document-row IDs are source-local identifiers, not canonical model equivalence. See [the inventory schema and retention policy](docs/data-collection.md).

This is **storage normalization**, not universally comparable cost normalization. Every row is marked `comparison_eligible: false` until separately curated. Reviewed comparisons remain at 12 models/71 offerings. The Providers view exposes the wider warehouse without promoting native rates into the calculator. Sources are scoped listings, not proof of exhaustive commercial availability; existing AWS/Azure regions remain unchanged. See [dashboard organization and projection rules](docs/dashboard-data-organization.md).

`provider_inventory.json` indexes current catalogs. `inventory_history.jsonl` records first discoveries and subsequent meaningful record/billing-condition changes; identical model lists with reordered JSON or changed HTML scripts do not create versions. `collection_checks.jsonl` retains small success/failure check records. Source-row absence is recorded as “no longer listed”, not an inferred vendor delisting. Existing curated CSV observations and all pre-existing raw source files are preserved unchanged; new unchanged daily observations are no longer appended.

New raw public-source responses may be written as gzip files with `--response-dir`; scheduled collection uploads them as Actions debugging artifacts expiring after **7 days**, never permanent Git blobs. Authenticated model-catalog responses are not uploaded. Existing `provider_sources/` is a read-only legacy archive, referenced explicitly in the migrated index. One early legacy JSON artifact predates exact-body storage; it is not independently byte-rehashable.

With `--archive-lookups`, changed public-document catalogs receive best-effort Wayback references. A capture is “verified” only if its exact target and fetched source-body hash match; nearest-date captures with different contents remain `content_mismatch`, and outages/missing captures remain `unavailable`. No keys, authenticated responses or assembled API feeds are submitted to Archive.org. Capture time and observation time remain distinct. Original inventory/history files and raw archives are not copied by Vite. It generates validated, read-only public catalog projections: a lightweight index and lazy model listings, provider details, histories, and separate change feeds. The comparison landing page does not download the warehouse.

## Official sources and parsing

| Provider | Source | Parser notes |
| --- | --- | --- |
| DeepInfra | [Public model API](https://api.deepinfra.com/models/list) | Cents/token × 10,000 → USD/1M. Published cache/tier multipliers are retained; precision/context come from API fields. |
| Novita | [Public model API](https://api.novita.ai/v3/openai/models) | Uses explicit `price_per_m_decimal` USD values, **not** similarly named integer billing-unit fields. |
| Together AI | [List Models API](https://docs.together.ai/reference/models) / [serverless docs fallback](https://docs.together.ai/docs/serverless-models) | API `pricing.input`, `output`, optional `cached_input` in USD/1M for text models; other modality/billing fields remain raw. Exact IDs and published context; no fabricated precision. Requires `TOGETHER_API_KEY`. |
| Fireworks | [Serverless catalog API](https://github.com/fw-ai/fireconnect/blob/main/packages/setup-cli/lib/fireworks/models.mjs) / [pricing docs fallback](https://docs.fireworks.ai/serverless/pricing) | Complete paginated `/v1/serverless/models` without a coding-only filter. Per-mode input/cache/output SKUs with explicit `1M tokens` units; Standard and Priority quoted, Fast/Spot retained raw. Requires `FIREWORKS_API_KEY`. |
| Groq | [Supported model Markdown](https://console.groq.com/docs/models.md) | Fetches official machine-readable `.md` rather than HTML. “Contact Sales” entries are excluded, never assigned invented list prices. Models API metadata does not contain prices. |
| OpenAI API | [Official pricing](https://developers.openai.com/api/docs/pricing) | Official `.md` Standard table; pinned GPT releases, explicit short/long prompt rates, never Batch/Fast rates relabeled Standard. |
| Anthropic API | [Official pricing](https://platform.claude.com/docs/en/about-claude/pricing) | Base-input/output and distinct cache-read/5-minute cache-write rates. First-party global endpoint. |
| Google Gemini API | [Official paid pricing](https://ai.google.dev/gemini-api/docs/pricing) | Paid Standard/Priority/Flex tables, not free or Batch tiers. Introductory prices selected by UTC date; token-hour cache storage is not a cache token rate. |
| Google Vertex AI (GCP) | [Cloud Billing Catalog API](https://docs.cloud.google.com/billing/v1/how-tos/catalog-api) + [official pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing) | With `GOOGLE_CLOUD_BILLING_API_KEY`, discovers Vertex service and archives every public USD SKU, unit, region and tiered price. Reviewed dashboard quotes retain semantic document tabs: Gemini global/non-global tiers and dated promotions; Claude Global only. No speculative SKU-to-model mapping. |
| Amazon Bedrock (AWS) | [Official pricing](https://aws.amazon.com/bedrock/pricing/) and public AWS Price List feeds | `AmazonBedrock` and `AmazonBedrockFoundationModels` US East (N. Virginia) catalogs. Explicit USD/1K or USD/1M units; Bedrock Runtime, global/regional Claude quotes, no inferred first-party pricing. |
| Microsoft Foundry (Azure) | [Public USD retail meters](https://prices.azure.com/api/retail/prices) | Complete East US `Foundry Models` service inventory, including Azure OpenAI and other Azure-metered model families. All published units/capacity/reservation meters are retained natively. Dashboard quotes remain reviewed OpenAI consumption USD/1M groups: Global/US Data Zone and Standard/Priority/long-context; Batch, reservations and provisioned units are not calculator quotes. Marketplace-only partner prices and Foundry Tools are outside this feed. |

Every observation includes the official URL, UTC timestamp, currency, and SHA-256 of its source payload. Multi-feed/page collectors hash the complete assembled JSON response. Sources can change layout: parsers fail closed on ambiguous units, invalid rates, unsupported price tables, or an empty tracked snapshot. Fixture tests cover each parser without making network requests.

Vertex's regional Claude tables currently contain conflicting unlabeled input/output rows, so the collector conservatively excludes them rather than guesses. The unambiguous Global Claude tab is tracked, including its four-column layout and six-column layout with separate 200K/100K prompt bands. Reviewed Claude 4.x quotes use only the explicitly labeled USD/1M-token 200K columns; a tracked model acquiring 100K-band prices fails closed pending review. Other regions and provider offerings are not claimed to be exhaustive. Model-version/capacity references are linked from the model selector; cloud endpoint capacities stay unverified when the source does not establish them.

### Failure and availability policy

- Each provider snapshot is fully validated **before** modifying data.
- A failed provider retains its last good prices and records the error in `status.json`.
- Observations over 48 hours old and failed collectors are explicitly marked in the UI.
- Removal detection applies only to successful full public catalogs (DeepInfra, Novita). Authenticated Together/Fireworks catalogs can be visibility-scoped, and document fallbacks are not equivalent full availability catalogs. They and all native/cloud pricing collectors remain conservative about removals.
- Empty snapshots never retire all offerings. If a provider removes its last tracked model, manual verification is needed; the collector will report failure rather than infer a mass delisting.
- New/removed/restored offerings, metadata changes, and price changes have distinct events. Missing cache prices are `null`, never zero.
- Curated history appends only first observations and actual price changes, including intraday changes/reverts. Freshness is updated separately in latest prices/status and check logs. Old CSV rows remain unchanged.
- `--strict` returns nonzero if **any** provider fails; otherwise a partial collection succeeds if at least one provider succeeds. All-provider failure always returns nonzero.

```bash
python -m scripts.collect --provider novita --provider deepinfra
python -m scripts.collect --dry-run --strict
python -m scripts.collect --data-dir /tmp/price-watch-experiment
```

Do not run concurrent collectors on the same directory. Unix runs also use a file lock; the workflow has a concurrency guard.

## Calculation assumptions

`input tokens` includes the cached portion. For USD-per-million rates:

```text
cached_input   = input_tokens × cache_hit_percent / 100
uncached_input = input_tokens − cached_input

cost_per_request = (
    uncached_input × input_rate
  + cached_input × (cache_read_rate, or input_rate if unpublished)
  + output_tokens × output_rate
) / 1,000,000

cost_per_million_requests = cost_per_request × 1,000,000
workload_cost            = cost_per_request × number_of_requests
```

Cache-write fees are visible but **not** included; the calculator assumes an already-populated cache. Claude cache-write quotes use a **5-minute TTL**; 1-hour writes are not mixed in. Cache storage per token-hour, grounding, and server-side tool fees are excluded.

Prompt-price bands use the **entire input, including cached tokens**. GPT-5.4 uses short pricing through 272,000 input tokens and long pricing above that. Inapplicable bands have no estimate and cannot win. Known combined context checks include input **plus** output; known output caps are checked separately. Gemini's documented 1,048,576 input / 65,536 output limits are separate and are not fabricated into a combined context window. Unknown cloud endpoint capacities remain explicitly unverified, not assumed unlimited.

Gemini 3.8 Flash's introductory pricing is observed through December 31, 2026; collectors switch to the explicitly published January 1, 2027 rates on that UTC date, without backfilling future or past observations. There is no latency/quality equivalence claim, tax estimate, negotiated pricing, credit accounting, or inferred batch discount.

## Storage and architecture

```text
catalog/models.yaml           canonical models
catalog/aliases.yaml          exact manually reviewed aliases
providers/*.py                independent official-source parsers
scripts/normalize.py          canonical IDs, validation, stable offering IDs
scripts/detect_changes.py     event generation
scripts/collect.py            collection + storage + failure handling

data/models.json              generated model catalog
data/offerings.json           current offering metadata, including inactive offerings
data/latest_prices.json       last successful price for every known offering
data/price_history.csv        append-only history of record
data/price_history.json       derived browser-friendly history cache
data/changes.json             append-only, deduplicated event feed
data/status.json              run time, curated coverage, errors, response hashes
data/provider_inventory.json  latest successful full-inventory index
data/provider_catalogs/       current full source-native pricing records
data/inventory_history.jsonl  append-only native inventory changes
data/collection_checks.jsonl  small success/failure check ledger
data/provider_sources/        pre-existing, read-only legacy source snapshots

dashboard/src/                static React app
.github/workflows/collect.yml  daily observations (06:17 UTC)
.github/workflows/deploy.yml   GitHub Pages build + deploy
.github/workflows/ci.yml       tests + typecheck + production build
```

Vite publishes only the seven normalized dataset files. Full, uncurated provider snapshots remain in the repository and are not served to dashboard visitors until a separate curation/presentation decision. There is no server endpoint or SQL database: the versioned JSON files in Git are the project's data store. `PAGES_BASE_PATH` supports project Pages, user Pages, or another static subdirectory. The dashboard fetches files at runtime, so data is separate from the app bundle.

### Add a model or provider

1. Add the model in `catalog/models.yaml` and explicit, reviewed provider IDs in `catalog/aliases.yaml`. Do not merge thinking/instruct versions or infer aliases by substring.
2. Add a provider module with `collect(aliases)` and pure `parse(body, aliases)` functions returning a `Collection`. Reuse `providers.common` helpers.
3. Register the provider and display name in `scripts/collect.py`, then add its color/initials in `dashboard/src/lib/data.ts`.
4. Add full-inventory adaptation in `scripts/catalog_inventory.py` and representative fixtures/tests. Mark a catalog authoritative only when it supports absence-based availability detection; full-inventory record absence is not vendor delisting.
5. Run a strict collection, review native inventory changes and curated differences, and run checks before publishing.

## Tests and production build

```bash
npm run check                # TS unit tests, Python unit tests, typecheck, build
npx playwright install chromium
npm run test:e2e             # real-browser flows, downloads, failures, mobile, dark mode
npm run preview             # serves the production build on :4173
```

Browser screenshots and failure traces go to ignored `test-results/`. Browser checks include WCAG 2.1 AA automated accessibility checks. Unit tests test pure cost arithmetic, null cache behavior, context constraints, units, alias safety, snapshot atomicity, history preservation, delisting/reactivation, malformed sources, cloud currency/units, prompt-band boundaries, output caps, dated promotion transitions, trusted pagination, CSV exports, and stale data.

On older Linux distributions unsupported by the latest Playwright installer, use an existing compatible Chromium executable:

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/path/to/chrome npm run test:e2e
```

```bash
PAGES_BASE_PATH=/tokentokentoken/ npm run build
```

`dist/` can be deployed to any static host. No secrets are required for the build or dashboard; optional pricing API credentials are collector-only. Fonts are self-hosted with system-font fallbacks; the dashboard makes no third-party runtime requests. Prices and fonts are served locally from the built artifacts.

## Collection-first GitHub setup

The selected production repository is **`yogenpro/token3` (public)**. Collection runs at **06:17 UTC daily**, with manual dispatch available. The workflow uses pinned action commits, read permissions by default, a write token only for the collection job, a 20-minute timeout, and a concurrency guard. It commits normalized data/check health even on a partial collector failure, then marks the run failed so GitHub can notify watchers.

Optional Actions secrets are `TOGETHER_API_KEY`, `FIREWORKS_API_KEY`, and `GOOGLE_CLOUD_BILLING_API_KEY`. Missing keys use explicit official-document fallbacks; no paid database, R2 bucket or Archive.org credential is required. Configure repository notification preferences to receive failed-run alerts.

For another installation, create/push a repository deliberately:

```bash
git add .
git commit -m "Build TokenTokenToken pricing dashboard"
gh repo create token3 --public --source=. --remote=origin --push
gh workflow run collect.yml --ref main
gh run list --limit 5
```

Workflows expect the default branch to be `main`. The collection workflow commits using `GITHUB_TOKEN`; no PAT is baked into the project. Protected branches may require allowing the bot to push or switching to reviewed data PRs. Scheduled Actions are best-effort and may be delayed or disabled after prolonged repository inactivity; dispatch manually if needed.

**Dashboard deployment is intentionally off.** `deploy.yml` is manual-only and additionally requires repository variable `ENABLE_PAGES=true`; Pages must be configured separately before dispatch. Collection does not depend on Pages. GitHub-token data commits do not trigger ordinary push CI workflows, so collector tests run within every collection job.

The public Pages site may be public even for a private repository depending on your GitHub plan. Check visibility before publishing.
