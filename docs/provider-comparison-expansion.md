# Provider comparison review — 2026-10-26

The user requested Compare coverage for all fourteen previously inventory-only
provider groups, including DeepSeek. This review adds selected exact model/source
bindings and independent quote adapters. It does not promote the native warehouse:
every native record remains `comparison_eligible: false`.

## Earlier decisions and present scope

The October 4 discussion deferred curation/display until after broad collection;
it was a sequencing decision, not a permanent provider ban. The October 11 review
left the remaining sources native-only because their routing, units, currency,
table alignment or model bindings had not been separately reviewed. Those were
explicit technical/economic gaps, not evidence that the providers were unsuitable.

Together is a different case: on October 18 the user declined its API deposit and
asked to table it if the free document could not refresh its quotes. Its comparison
pause, document-only collection and retained history remain intact. This expansion
does not contact its gated API, spend money, activate gates or authorize deployment.

## Reviewed sources and billing interpretations

This is a bounded initial selection across all requested providers, not all of each
provider's models, modalities, tiers or regions. Exact source IDs are declared in
[`catalog/aliases.yaml`](../catalog/aliases.yaml); prices always come from the
fetched source, never a hardcoded price list or a native-record projection.

| Provider | Selected comparison scope | Billing basis and conditions |
| --- | --- | --- |
| OpenRouter | GPT-OSS 120B/20B, Llama 3.3 70B Instruct | [Public catalog](https://openrouter.ai/api/v1/models), advertised USD/token × 1,000,000. Gateway/default routing is explicit; no particular supplier is inferred. Negative dynamic prices, extra billing components and unsupported conditions fail review. Credit-purchase fees are additional and excluded. |
| Alibaba Cloud Model Studio | GLM-5.3 | [Official pricing](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/model-pricing.md), Singapore International flat USD/1M input/output schedule for Non-Thinking and Thinking modes. Other regional tabs, prompt schedules and cache discounts remain native-only. |
| Hugging Face Inference | GPT-OSS 120B, Qwen3.8 27B, GLM-5.3/Flash, dated DeepSeek V4 Pro 0813 | [Router catalog](https://router.huggingface.co/v1/models) and [billing guide](https://huggingface.co/docs/inference-providers/pricing). Explicitly selected live Novita routes only, billed through Hugging Face in USD/1M; no automatic cheapest-supplier selection or inferred direct Novita quote. |
| Snowflake Cortex | Claude Opus 5.5, GLM-5.3, Kimi K3 | [Consumption PDF](https://www.snowflake.com/legal-files/CreditConsumptionTable.pdf), Table 6(b), Cortex Inference with Prompt Caching. AI Credits per million tokens remain AI Credits, separately from Platform Credits. Matched model rows and Input/Output/Cache Write/Cache Read column order are validated. The reviewed `5` footnote marker is matched explicitly; arbitrary suffixes are never stripped. Routing/contract credit-to-money conversion is excluded. |
| Cloudflare Workers AI | GPT-OSS 120B/20B, Llama 3.1 8B base/FP8, Llama 3.3 70B FP8 Fast, Qwen3.8 27B, GLM-5.3/Flash | [Official token-price column](https://developers.cloudflare.com/workers-ai/platform/pricing/), USD/1M. These are published token prices, not an invented neuron conversion. Exact precision/route IDs remain separate. Free allocations and account/plan fees are excluded. |
| Databricks | GPT-OSS 120B/20B, Llama 3.3 70B, Llama 3.1 8B | [Foundation Model Serving](https://www.databricks.com/product/pricing/foundation-model-serving), Standard pay-per-token DBU/1M. Both merged-header rows must establish Input, Output and Cache read alignment. No example USD/DBU rate is generalized to all accounts/clouds/regions. Hourly, provisioned, Priority and Batch products remain outside this selection. |
| Oracle Cloud Generative AI | GPT-OSS 120B/20B | [Public USD price list](https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/?currencyCode=USD). Exact SKU pairs B112004/B112005 and B112006/B112007, metric `1,000,000 Tokens`, USD and PAY_AS_YOU_GO must all match. No transaction/token conversion or inferred endpoint availability. |
| Nebius Token Factory | GPT-OSS 120B, Qwen3.8 27B, GLM-5.3/Flash, dated DeepSeek V4 Pro 0813 | [Official catalog](https://tokenfactory.nebius.com/api/public/models_info), USD/1M for explicitly reviewed `cheap` flavors and regions; actual precision, context and cached-input rates preserved. No private/external flavor or inferred mutable-version equivalence. |
| xAI | Grok 4.7 | [Official text API table](https://docs.x.ai/developers/pricing), Standard USD/1M; `<200,000` and `≥200,000` full-prompt schedules remain separate. Priority, regional, Batch, voice and tools are excluded. |
| Z.ai | GLM-5.3, Flash, FlashX | [International API pricing](https://docs.z.ai/guides/overview/pricing.md), explicit USD/1M input/output/cache-read columns. Storage promotions, Coding Plan subscriptions and Chinese Zhipu billing are separate. |
| OVHcloud AI Endpoints | GPT-OSS 120B/20B | [Explicit EUR website price cards](https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/), EUR per million input/output tokens. These are independently collected reviewed quotes. The original API catalog's absent currency remains unverified; no currency is assigned to its native amounts by association. |
| Scaleway Generative APIs | GPT-OSS 120B | [Public catalog](https://api.scaleway.com/product-catalog/v2alpha1/public-catalog/products?page_size=1000), realtime `fr-par` EUR retail input/output SKU pair. EUR money per 1,000 tokens × 1,000; no FX conversion. Batch, dedicated nodes and unreviewed statuses remain native-only. |
| MiniMax | MiniMax M3 | [International pay-as-you-go table](https://platform.minimax.io/docs/guides/pricing-paygo.md), published permanent-discount USD/1M, Standard/Priority × `≤512,000`/`>512,000` full-prompt bands. Original struck-out rates are validated against the explicit 50% expression; they are not current quotes. Missing bands fail the complete snapshot. |
| DeepSeek | Flash served as V4.1-Flash-1017, Pro served as V4-Pro-0813 | [Canonical pricing URL](https://api-docs.deepseek.com/quick_start/pricing/), USD/1M with both peak/off-peak scenarios, cache hit/miss, served versions and exact UTC/Chinese-public-holiday schedule. No local-time or holiday-calendar inference. Mutable served-version or schedule changes require new review. |

## Compare, history and exports

Compare has a shareable billing-basis selector: **USD, EUR, Databricks DBUs or
Snowflake AI Credits**. Rankings, summary minima, workload maps, history and CSV
exports use one basis at a time. EUR prices are never labeled dollars, and credits
are never labeled currencies. There is no FX feed or assumed USD/DBU conversion.
USD remains the default; the model directory's summary prices remain USD and label
that scope explicitly. Reviewed JSON exports include all bases with their metadata.

Non-USD offerings have explicit `quote_unit`; legacy offerings default to USD.
Snowflake's selected rows carry footnote 5 (Preview, subject to Preview Terms),
which is preserved in their variant and notes. Databricks' [supported-model
reference](https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/supported-models)
establishes the Instruct identities behind its abbreviated Llama pricing labels.
Monetary prices retain `currency: USD/EUR`; native credit quotes have `currency:
null` and their unit on the offering. The CSV history keeps its existing columns,
with an empty currency for credit units; join offering IDs to `offerings.json` for
the basis. Offering IDs distinguish non-USD bases, preserving every original ID.
Comparison CSV column names identify the selected basis and append `quote_unit`.
No export joins unlike currencies into an apparent monetary comparison.

DeepSeek defaults to the explicitly labeled **peak scenario**. Visitors can choose
off-peak; the selector is preserved in the URL and applied to rankings, the price
map and history. This is a scenario, not a claim that the selected period currently
applies. Both rates stay visible through their corresponding selection and source
notes. Its historic document identity keeps the original URL while retrieval uses
the working trailing-slash URL; this avoids manufacturing native remove/add events.

## Integrity and validation

New quotes start at their real successful collection time. Original reviewed CSV
rows, JSON observations, offering IDs, native history, legacy archives and source
hashes are preserved; this review performs no historical backfill. Last-good
reviewed prices survive incomplete/ambiguous snapshots, independently of whether
valid native evidence can still be retained. Unsupported schedules and missing
currency remain unknown rather than cheap/free.

Bounded exact public excerpts and parent capture hashes are in
`tests/fixtures/provider-comparisons/manifest.json`. They are regression inputs,
not production source captures or backfills. Tests cover complete bindings,
identity isolation, malformed units/currencies, unknown components, duplicates,
missing routes/bands, version/schedule changes, native comparison isolation,
last-good retention, currency/unit ranking separation and export labels. Live
verification uses a provider-scoped strict dry-run before a legitimate collection.

Remaining native-only scope is deliberate at the **record** level: embeddings,
image/audio/video, dynamic routing, unreviewed models/regions/tiers, hourly capacity,
unknown amounts/units and unsupported billing formulas do not become token quotes.
An active reviewed quote does not establish account access, vendor performance or
current availability of every native listing.
