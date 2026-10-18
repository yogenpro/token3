# Source-native provider expansion

The source warehouse collects **26 provider groups**: the original 11 plus the 15 below. The original expansion was **collection only**. A subsequent [2026-10-11 explicit model review](reviewed-model-review.md) added separately curated Vercel gateway quotes and expanded reviewed coverage to **45 models / 216 offerings across 12 billing providers**. The other 14 expanded sources remain inventory-only; every native row, including Vercel rows, remains comparison-ineligible. Discovery never creates a canonical alias, quote or cross-provider equivalence automatically. Google Gemini Developer API and Google Vertex AI remain separate sources and commercial offerings.

The existing source-native catalog/index and change-only history are reused. A later storage/presentation design can work from the collected evidence; this step does not introduce a database or universal cost schema.

## Sources and deliberate boundaries

| Provider | Selected official source | Collection and caveats |
|---|---|---|
| OpenRouter | [Public models API](https://openrouter.ai/api/v1/models), [field semantics](https://openrouter.ai/docs/guides/overview/models) | Every advertised model, native per-token prices, cache fields, overrides and modality metadata. Routing products with `-1` prices are explicitly dynamic/unknown, not free. Advertised model prices are not a guarantee of the price of a selected supplier endpoint. Per-supplier endpoint listings and credit-purchase fees are outside this selected catalog. |
| Vercel AI Gateway | [Public models API](https://ai-gateway.vercel.sh/v1/models) | All exposed language, embedding, image, video and audio models. Preserve token rates, prompt tiers, regional/provider-dependent prices, service tiers and other billing components. No selected upstream route is inferred. |
| Alibaba Cloud Model Studio (Qwen) | [Official model pricing Markdown](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/model-pricing.md) | Complete returned standard-price tables, including regional MDX tabs, prompt bands, caching and non-text modalities. Qwen is a model family hosted by this service, not a separate billing provider. No console-only promotion, currency conversion or China/international equivalence is inferred. |
| Hugging Face Inference | [Public router chat-model catalog](https://router.huggingface.co/v1/models), [billing guide](https://huggingface.co/docs/inference-providers/pricing) | Every returned model/provider route is a separate native record. The router supplies token prices in USD per million tokens where available. Missing prices remain unknown even when a route has an `is_free` flag. This is not the full multimodal Hub catalog. `hf-inference` compute seconds, illustrative hardware rates and dedicated endpoints are not normalized into token prices. |
| Snowflake Cortex | [AI pricing guide](https://docs.snowflake.com/en/user-guide/snowflake-cortex/pricing.md), [Service Consumption Table PDF](https://www.snowflake.com/legal-files/CreditConsumptionTable.pdf) | Preserve AI Credit vs Platform Credit rules and the complete PDF as source-native page text. The exact PDF response-byte SHA-256 is retained separately in `source_evidence`. PDF table alignment and model-to-rate mapping remain unreviewed. An unavailable PDF produces an explicit guide-only, limited-coverage fallback; it cannot replace a previously collected full PDF catalog. No contract-specific credits-to-USD estimate is made. |
| Cloudflare Workers AI | [Official pricing Markdown](https://developers.cloudflare.com/workers-ai/platform/pricing/index.md) | Public model/modality tables and neuron billing rules. Neurons, token rates and free allowances remain distinct; no model-specific neuron-to-token conversion is guessed. |
| Databricks | [Open model serving prices](https://www.databricks.com/product/pricing/foundation-model-serving), [proprietary model serving prices](https://www.databricks.com/product/pricing/proprietary-foundation-model-serving) | Both returned public price tables, with DBU/token, capacity, cloud and region context. Native DBUs are not relabeled USD. A dollar-per-DBU conversion, deployment availability or contract discount needs separate review. |
| Oracle Cloud Generative AI | [Public USD OCI price-list API](https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/?currencyCode=USD) | All returned Generative AI SKUs, part numbers, native billing metrics and PAYG/other published price models. Transaction/character/token and dedicated AI-unit metrics are not conflated. The full OCI infrastructure catalog is fetched for filtering but not retained as inference inventory. |
| Nebius Token Factory | [Authoritative public catalog](https://tokenfactory.nebius.com/api/public/models_info), [catalog documentation](https://tokenfactory.nebius.com/model-catalog.md) | Every exposed model flavor and region, preserving exact IDs, quantization, token prices and native fields. Private custom models and general GPU infrastructure pricing are excluded. Live performance/quality measurements do not create pricing history noise. |
| xAI | [Official API pricing](https://docs.x.ai/developers/pricing) | Complete returned text, image, video, voice and tool tables, including prompt bands, batch/regional modifiers and billing prose. Authenticated model-price feeds require a separately reviewed adapter; the current source needs no key. |
| Z.ai | [International API price tables](https://docs.z.ai/guides/overview/pricing.md) | Published models, tools, storage rules and promotions in the international API document. Chinese Zhipu billing and Coding Plan subscriptions are different products and are not silently substituted. |
| OVHcloud AI Endpoints | [Public Catalog API](https://catalog.endpoints.ai.ovh.net/rest/v1/models_v2), [API documentation](https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-catalog-api.md) | All returned models, including unavailable entries, their aliases/modalities, and native prices/units. **The catalog JSON does not state the currency.** Preserve the amounts in `billing.native_rates` with unknown currency; do not invent USD or assume EUR from another page's locale. A later currency reconciliation can use additional official evidence. |
| Scaleway Generative APIs | [Public SKU catalog](https://api.scaleway.com/product-catalog/v2alpha1/public-catalog/products?page_size=1000), [API documentation](https://www.scaleway.com/en/developers/api/product-catalog/public-catalog) | Complete catalog pagination, selecting exactly `Generative APIs` and `Inference Dedicated`. Preserve EUR structured money, units/sizes, locality, token direction, batch/realtime modes and lifecycle metadata. Unpriced/free-tier/retired SKUs are unknown, not invented zero-cost rates. A native `node` unit is not assumed to mean an hour. |
| MiniMax | [International pay-as-you-go pricing](https://platform.minimax.io/docs/guides/pricing-paygo.md) | All returned text, image, speech, music/video and other modality tables, prompt bands, caching and discount expressions. Subscription/Token Plans and Chinese-region offers are outside this document. |
| DeepSeek | [Official models/pricing table](https://api-docs.deepseek.com/quick_start/pricing) | Complete transposed model table plus tool prices and notes. Validate exact model columns/versions and all six peak/off-peak token components; reject tool-only/partial pages. Preserve original rows plus explicit native model records with exact API IDs, served versions, original capacity strings, UTC schedule and Chinese-holiday exception. No current-period inference, canonical alias or calculator quote is created. |

All 15 sources currently work **without additional credentials**. None of their model inference endpoints is invoked. Public model/list/price calls do not purchase credits or create cloud resources.

## Capture, identity and retention

- Fourteen expanded providers explicitly return `inventory_only=True`; the orchestrator rejects any such collector that tries to publish dashboard observations or retire offerings. Zero reviewed offerings is a successful collection, not an empty-price failure. Vercel's separately registered quote adapter requires explicit source bindings and full quote validation; its advertised catalog is not authoritative for retiring old reviewed offers.
- Source responses are assembled in an internal transport envelope. That envelope is not a new storage design: the persisted records still use the existing source-native schema, `comparison_eligible: false`, and existing revisioned history.
- Public API lists must be complete. OpenRouter totals/next-page markers are checked. Scaleway validates the whole paginated SKU count, unique SKUs and unchanged totals before selecting AI categories. Bounded response/catalog limits still apply.
- Document source URLs, headings, tabs, original columns/cells, conditions and prose are retained. MDX region tabs and HTML/Markdown mixed tables do not lose their scope. Native DBU/credit/EUR amount changes retain stable row identities where the source establishes identity; no price-independent mapping is claimed for unlabeled ambiguous occurrences.
- Gateway regional/tier overrides and complicated multimodal formulas remain in `billing.rules`, even where only reviewed scalar units can be exposed in `rates`. An empty `rates` list does not mean free.
- Hugging Face latency/throughput, Nebius throughput/quality and OVH benchmark measurements are not price history inputs. Model/price/rule/capacity changes remain meaningful observations.
- PDF page text is not a parsed, column-aligned price table. Its extraction method is explicit. The PDF's raw-byte hash is provenance, not a per-page pricing fingerprint.
- New raw responses are temporary public debugging artifacts, expiring after **7 days**, not new permanent source archives. Existing observations and the legacy archive are unchanged. Assembled multi-source envelopes are not submitted as if they were exact Wayback page captures.

## Live validation

The first live capture added **3,290 source-native records** across the 15 new providers, bringing the warehouse to **17,843 records / 26 provider groups**. Counts are records, not unique models; document rows, PDF pages, model flavors, routes and SKUs are intentionally different kinds of evidence.

Snowflake's initially blocked consumption PDF succeeded on retry: **24 pages** were retained along with the billing guide and exact PDF response hash. Existing dashboard files, all 11 previous native catalogs and all 20 legacy source archives were byte-identical after the expansion; inventory history was appended, not rewritten.

A second live capture left **13 of the 15 new catalogs byte-identical**. OpenRouter reported one advertised Kimi K3 price change; Hugging Face added two routes and stopped listing one, producing four meaningful inventory events rather than duplicate daily snapshots. Route absence is not proof of vendor/model delisting. No inference requests were made.

## Operational notes

Use Python **3.12 recommended; 3.9+ required** with the pinned requirements. `pypdf` is used only to read Snowflake's official consumption table. PDF responses are bounded to 8 MiB, at most 100 pages and 8 MiB of extracted text. The original bytes are hashed before extraction.

Run only these expanded source groups (Vercel also validates its explicitly reviewed token quotes):

```bash
python -m scripts.collect --strict \
  --provider openrouter --provider vercel --provider alibaba \
  --provider huggingface --provider snowflake --provider cloudflare \
  --provider databricks --provider oracle --provider nebius \
  --provider xai --provider zai --provider ovhcloud --provider scaleway \
  --provider minimax --provider deepseek
```

The normal scheduled command selects all **26** providers automatically. Health distinguishes inventory-only collection from reviewed quotes, and limited optional-source coverage is visible. A separate, review-pending data-only publication path can follow successful strict collection after deliberate activation; it is off (`ENABLE_COLLECTION_PUBLISH=false`). This is not permission to publish new code or partial data. See [publishing](publishing.md).
