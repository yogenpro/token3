# Pricing source/API capability review

Collection should prefer official structured rate catalogs. A model-list API that only returns IDs/capabilities is not a pricing API, and a usage/cost API reports incurred account charges rather than current public list rates. A gateway quote is labeled as that gateway's billing price, never substituted for an originating provider's direct quote. Native discovery remains separate from explicit reviewed source bindings.

## Original quote sources and Vercel

| Provider | Structured pricing source | Current strategy | Credentials |
| --- | --- | --- | --- |
| DeepInfra | `GET https://api.deepinfra.com/models/list`, including original pricing objects | Already API-based, complete returned catalog retained | None |
| Novita | `GET https://api.novita.ai/v3/openai/models`, including decimal prices and units | Already API-based, complete returned catalog retained | None for this public listing |
| Together AI | Retained `GET https://api.together.ai/v1/models` adapter with `pricing` objects | **Comparisons paused**; free serverless document inventory only, no deposit-gated API call | None in current mode; API resumption requires separate review |
| Fireworks | `GET https://api.fireworks.ai/v1/serverless/models`, with per-mode `pricing` SKUs | API-first, complete pagination, no use-case filter; official pricing Markdown fallback | `FIREWORKS_API_KEY` |
| Groq | Documented `/openai/v1/models` schema has IDs/metadata, no list prices | Official `/docs/models.md`; HTML no longer needed for normal collection | No key for pricing document |
| OpenAI API | Documented `/models` response has model metadata, no list prices | Official Standard `.md` tables; validated legacy, split-retention and compact layouts. Current labelled writes use the explicitly reviewed 30m scope; 12h stays native-only | No key for pricing document |
| Anthropic API | Documented `/v1/models` response has capabilities/token limits, no list prices | Official pricing `.md` tables | No key for pricing document |
| Google Gemini API | Documented `models.list`/`Model` resource has capabilities/token limits, no list prices | Official Gemini Developer API pricing `.md.txt` | No key for pricing document |
| Google Vertex AI | Cloud Billing Catalog API `v1/services` and `v1/services/{id}/skus` | Complete USD SKU inventory with a key, plus pricing document for existing reviewed dashboard quotes; document-only fallback | `GOOGLE_CLOUD_BILLING_API_KEY` |
| Amazon Bedrock | Public AWS Price List bulk JSON catalogs | Already structured feeds (`AmazonBedrock` and `AmazonBedrockFoundationModels`, `us-east-1`) | None |
| Microsoft Foundry (Azure) | Azure Retail Prices API, `serviceName eq 'Foundry Models'` | Complete East US public USD service meters, including Azure OpenAI and other model families; reviewed OpenAI dashboard mappings stay separate | None |
| Vercel AI Gateway | Public `GET https://ai-gateway.vercel.sh/v1/models` | Complete native catalog plus separately curated language-model token quotes with exact source IDs, prompt bands and Standard/Flex/Priority prices; no supplier-route inference | None |

This is an API capability review, not a claim of exhaustive commercial coverage. The providers, source scopes and original units remain explicit. Authenticated listings may be account-scoped. Region scopes for existing Azure/AWS collection are unchanged.

## Source-native expansion and separate quote review

The 15 additional source groups use selected public pricing catalogs/documents with no new credentials: OpenRouter, Vercel AI Gateway, Alibaba Cloud Model Studio, Hugging Face Inference, Snowflake Cortex, Cloudflare Workers AI, Databricks, Oracle Cloud Generative AI, Nebius Token Factory, xAI, Z.ai, OVHcloud, Scaleway, MiniMax and DeepSeek. All enrich the native warehouse; selected scopes across all fifteen now have separately curated quote adapters. The [2026-10-26 review](provider-comparison-expansion.md) documents exact bindings and isolated USD/EUR/DBU/AI Credit bases. Native records still never enter comparisons directly. See [all source URLs, native units, scope boundaries and operational caveats](collection-expansion.md). Google Gemini Developer API and Vertex AI remain separate pricing sources.

The [2026-10-11 recent-model review](reviewed-model-review.md) added 33 identities while preserving the original coverage. Source permission is explicit in `catalog/aliases.yaml`; a model alias present globally is not a price binding for every source. Newer AWS/Vertex/Foundry meters and unsupported source variants remain native-only.

## API details and limits

### OpenAI Standard table and cache-write scope

The [official pricing Markdown](https://developers.openai.com/api/docs/pricing.md) now reorders input/output/cache columns, separates 30-minute and 12-hour writes, and lists GPT-5.4 mini in a compact input/output/cached-input table. The 2026-10-21 failed capture and the 2026-10-22 investigation fetched the same body SHA-256: `129d6019819379a6f30edc0811d4631ddb085dcd4b3b1d0012a945cd1af1bfbf`.

The parser accepts only complete, distinct named columns from the three reviewed layouts. Standard's own preceding/in-section USD-per-million basis is required; a denominator in Batch cannot supply missing Standard evidence. Malformed/duplicate tracked rows, unknown/duplicate headers, missing known long-context prices and changed 272K boundaries fail closed. Exact source IDs, global region, Standard tier and known/unverified capacities remain unchanged; the compact table cannot erase a known long-prompt schedule.

The user explicitly approved **current 30-minute cache-write scope** during issue #3 investigation. All 11 retained quote identities and input/output/cache-read/selected-write amounts match this source interpretation. The equal amounts do **not** prove historical TTL equivalence: original unqualified write observations remain retention-unverified. Current quote notes state 30-minute retention; 12-hour components stay native-only and are never selected as a fallback or because they are cheaper. Cache writes remain excluded from workload estimates. Missing writes stay unknown (`null`), not free. No historical observations, prices or source hashes are rewritten; see [the dated scope review](reviewed-model-review.md).

### Vercel AI Gateway

The [REST reference](https://vercel.com/docs/ai-gateway/sdks-and-apis/rest-api) defines token costs and `[min,max)` ranges (inclusive minimum, exclusive maximum). Reviewed prices convert USD/token to USD/1M and preserve each integer prompt interval. Missing, overlapping, incomplete or conflicting schedules fail closed. [Service tiers](https://vercel.com/docs/ai-gateway/models-and-providers/service-tiers) are best-effort routing requests, not latency or actual-served-tier guarantees.

Only source-bound language identities and explicitly published Standard/Flex/Priority prices are quoted. Fast, ultrafast, regional, Batch and non-token components stay in the full native rules; no supplier endpoint is inferred. Cache-write TTL is unverified, not copied from another provider. Quote parsing can fail while the complete fetched native source is retained and last-good comparison prices remain intact. No inference API is called.

### Microsoft Foundry (Azure)

Microsoft's [Foundry Models overview](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure) states that models sold by Azure include all Azure OpenAI models and selected third-party models. The public [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) exposes their service as `Foundry Models`.

The collector now uses `serviceName eq 'Foundry Models' and armRegionName eq 'eastus'`, replacing the narrower OpenAI product-name filter. Live verification found **1,699 meters**, including all **1,248 prior OpenAI meter IDs** plus **451 additional meters**. Examples include DeepSeek, Llama, Mistral, Phi, Grok, Qwen, Kimi, Cohere, MAI and BFL Flux product families, plus managed-compute and provisioned-capacity products. These are meter counts, not unique model counts, and can change.

- Public USD retail prices, complete pagination, and the existing East US billing scope; no Azure account or key required.
- Native currencies, units, tiers, dates, reservations and service/product metadata remain explicit. Hourly capacity is not converted into token pricing.
- Provider ID `azure` and historical offering IDs remain stable. The dashboard label is **Microsoft Foundry**; reviewed GPT-5.4/mini comparisons remain Azure OpenAI quotes. Other families are not automatically treated as comparable dashboard offerings. Product identity is checked before matching OpenAI version-like SKUs.
- This feed is **not** the entire Foundry marketplace or platform: partner Marketplace offers may have separate pricing, Foundry Tools is a separate service, and managed compute can incur additional infrastructure charges. No negotiated rates or account-specific offers are collected.

### Together

The [List Models API reference](https://docs.together.ai/reference/models) explicitly describes model metadata **including pricing**. Text models expose `pricing.input`, `pricing.output`, and optional `pricing.cached_input`. The [official serverless catalog](https://docs.together.ai/docs/serverless/models) identifies USD-per-million text-token units.

**Current operating decision:** the user declined the API deposit. `config/provider_policies.json` pauses reviewed comparisons while retaining free document inventory. No authenticated request is made even if a local key exists. Old quotes/history and active flags remain retained, not treated as fresh/current comparisons or vendor delistings.

If separately resumed, the retained API adapter fetches the entire response for all model types, then retains its source-native pricing records in the full inventory (not a permanent authenticated raw-response archive). Only reviewed text model IDs enter the existing dashboard. Hourly, base, fine-tuning and non-text fields are not relabeled as text-token prices. Missing cache rates remain unknown. Because authentication can affect visibility, absence in this response does not automatically retire an existing offering.

### DeepSeek official API evidence

The [official pricing page](https://api-docs.deepseek.com/quick_start/pricing) is collected separately from all gateways. Its transposed model table is now validated for completeness and aligned into additional native model records; original rows remain. Six explicit cache-hit/cache-miss/output rates retain peak/off-peak conditions, exact served versions, UTC windows and the Chinese-public-holiday exception. The separate 2026-10-26 review adds explicit peak/off-peak scenario quotes, with exact served versions and schedule validation. It does not infer current applicability or rewrite history. Retrieval now uses the working [canonical trailing-slash URL](https://api-docs.deepseek.com/quick_start/pricing/), preserving the historic native document identity.

Evidence review on **2026-10-18** found Flash input/output rates of USD 0.15/0.60 off-peak and 0.30/1.20 peak per million tokens, matching our retained October 6 capture. The October 17 capture changed the served version to `DeepSeek-V4.1-Flash-1017` and added Search/Fetch rows. The October 18 Vercel reduction is a gateway quote, not evidence of a direct DeepSeek tariff reduction. These are dated findings, not permanent prices. No missing historical cut is fabricated or backfilled. Tool-only/partial snapshots now fail rather than replacing complete model evidence.

### Fireworks

The generic [List Models schema](https://docs.fireworks.ai/api-reference/list-models) describes `serverlessModes[].skuInfos`, but explicitly notes that pricing is populated by **ListServerlessModels**, not necessarily the generic management listing. The first-party [FireConnect client](https://github.com/fw-ai/fireconnect/blob/main/packages/setup-cli/lib/fireworks/models.mjs) uses `/v1/serverless/models` and opaque `nextPageToken`/`next_page_token` pagination. It documents flat USD decimal amounts and the `LLM input tokens (uncached)`, `LLM input tokens (cached)` and `LLM output tokens` SKU names.

Our collector omits the client's coding-only `use_cases` filter so returned non-coding modalities are retained too. It requires explicit `1M tokens` units for curated rates; structured Money values must specify USD. Missing or malformed base/output rates fail closed, not to zero. Standard/Priority remain separate. Fast, Spot, routers and non-token price dimensions are retained as source-native inventory records without inventing equivalence with existing dashboard offerings. Independently valid full-inventory records can survive a curated-parser error; full-inventory normalization failures retain the last good catalog. Incomplete or malformed pagination triggers an explicit fallback instead.

### Google Vertex

The [Cloud Billing Catalog guide](https://docs.cloud.google.com/billing/v1/how-tos/catalog-api) and [SKU-list reference](https://docs.cloud.google.com/billing/docs/reference/rest/v1/services.skus/list) provide public SKU descriptions, regions, pricing information, units, aggregation rules and tiered rates. Enable the Cloud Billing API for the key's project. The collector discovers the exact `Vertex AI` service, then retrieves all its USD SKU pages; it never filters to the dashboard's selected model aliases.

SKU descriptions alone are **not yet reviewed mappings** for model release, prompt-length band, endpoint geography, service tier or modality. The API data is therefore added to the uncurated inventory while the [official Vertex pricing document](https://cloud.google.com/vertex-ai/generative-ai/pricing) continues to establish existing dashboard quotes. Both sources are listed and hashed in the assembled source payload. API SKU fields are not guessed into token prices or substituted for Gemini Developer API rates. No billing-account or negotiated-pricing endpoint is called.

## Why four document sources remain

Reviewed documented model-list schemas:

- [OpenAI Models API](https://developers.openai.com/api/reference/resources/models/methods/list)
- [Anthropic Models API](https://platform.claude.com/docs/en/api/models/list)
- [Gemini Model resource](https://ai.google.dev/api/models)
- [Groq API reference](https://console.groq.com/docs/api-reference)

Those schemas do not expose list-price fields. This does not prove that no private/internal endpoint exists; it means no suitable official public pricing API was verified for these integrations. Using their pricing-document representations avoids browser automation, but still requires table parsing. We fetch official Markdown where available, retain its pricing rows/billing conditions rather than daily raw copies, and do not call authenticated model APIs merely to obtain the same unpriced identifiers.

## Operational behavior

- API keys are optional collector environment variables (see `.env.example`), never `VITE_` build variables.
- Keys are sent in headers. Authenticated redirects are rejected to prevent forwarding credentials. Keys are not placed in archived URLs or payloads; collection errors redact configured keys.
- Missing credentials/API request failures use an explicit documented-source fallback. `source_kind` and `fallback_reason` are saved to both collector health and the inventory index; the CLI prints the reason. A fallback with valid official prices is not a provider outage under `--strict`.
- Incompatible API pricing is not discarded in favor of a guessed conversion. Independently valid source-native inventory records can be retained; normalization failures keep the last good catalog. Previous curated prices/history remain intact.
- Pagination is bounded, detects repeated/conflicting tokens, and fails before applying partial listings. Full inventory and the curated dashboard remain separate.
- New public raw responses are temporary 7-day debugging artifacts, not committed snapshots. Authenticated model-catalog responses are excluded, known private models are rejected, and credential echoes/errors cannot be persisted. Existing legacy archives are preserved. See [storage and archive-reference policy](data-collection.md).
- Offline tests exercise API formats, pagination, auth-header propagation, fallbacks, failure retention and secret redaction. Live verification requires the corresponding credential; missing keys still produce explicit document fallbacks.

## Live API validation — 2026-10-06

[Successful hosted collection](https://github.com/yogenpro/token3/actions/runs/37429423042):

| Provider | Verified source | Snapshot coverage |
| --- | --- | --- |
| Fireworks | Authenticated `/v1/serverless/models`, no document fallback | 26 model/serving-mode rows: 25 with published monetary rates and one unpriced row |
| Google Vertex | Cloud Billing Catalog API plus reviewed pricing document, no fallback | 9,057 public USD SKUs plus 926 document rows |
| Together | Credential not configured | Existing official-document fallback remains active |

Counts describe that observation, not a fixed list of unique models. Fireworks can omit `pricing` for a product; such records retain native kind/pricing-mode metadata and unknown prices, never an invented zero. Malformed published pricing still fails closed. Its SKU ordering is normalized so reordering does not create price changes. Vertex SKU-to-dashboard mapping remains deferred; API prices are not guessed into canonical offers. All 11 collectors passed; original curated price history and legacy source archive files remained intact. No inference requests or billing-account queries were made.

For future schema troubleshooting, manually dispatch `inspect-fireworks.yml`. `scripts/inspect_fireworks_catalog.py` reports aggregate field shapes/counts and samples only reviewed public model prices. It has read-only repository permissions, does not write dataset files or save authenticated response bodies, and rejects configured credential echoes.
