# Provider and model coverage expansion — 2026-11-04

This review adds **18 public source groups**, **66 reviewed canonical identities**
and **100 first-observed offerings**. Retained coverage is **169 models / 447
offerings across 34 reviewed billing groups**, with bounded native evidence across
**47 source groups**. These are retained reviewed identities and source groups,
not counts of currently accessible endpoints or unique native models.

At this review, historical evidence remained scoped to the original **26 groups**.
The separately authorized [November 5 backfill](recent-provider-history.md)
subsequently expands the selected historical scope to 47 groups. Together remains
paused. Collection uses public documents/model/price listings, without new
credentials, inference calls, deposits, paid services or release-gate changes.

## Exact review selections

**November 13 operating update:** the original selections below remain retained
review evidence. Castform collection/current comparisons are stopped after no
verified replacement token-pricing feed was found. Arcee excludes only
`deepseek/deepseek-v4-pro-0813` and `zai-org/glm-5.2` from current quotes and
comparisons; the other three reviewed bindings remain mandatory. Native/history
evidence and availability flags are retained, without asserting retirement.
There are 46 enabled collectors within the retained 47-group directory. See
[source research and the operator policy](pricing-sources.md#november-13-collection-investigation-issue-35).

The [dated manifest](research/provider-model-expansion-2026-11-04.json) and
`tests/fixtures/provider-model-expansion/review.json` record the baseline, every
new identity and exact source bindings. Aliases in `catalog/aliases.yaml` grant
permission only to those named sources; another matching native ID is not a quote.

- **OpenRouter:** 61 separately selected text-output identities with simple
  USD/token prices. Cohere, StepFun, Liquid, Aion Labs, Inception, Writer, Tencent,
  Mistral, Qwen, DeepSeek, MiniMax and Kimi versions stay distinct. Conditional
  overrides, additional unsupported fees, absent IDs and non-text outputs are
  excluded. These are advertised gateway offers, without an inferred supplier.
- **Vercel AI Gateway:** 14 additional exact language-model bindings. Its complete
  native catalog still includes unreviewed products and modifiers. Existing
  Standard/Flex/Priority bands and source scope remain intact.
- **Cerebras:** two Shared Inference quotes, GPT-OSS 120B and Qwen 3.8 27B. The
  default public feed's per-token USD schema is independently checked. Feed and
  paid-reference capacities differ, so reviewed capacities stay unverified;
  native fields preserve the conflicting published scopes.
- **Castform:** eleven advertised inference quotes. Training, embeddings and the
  unresolved `hy3-rl` identity remain native-only. No upstream price, endpoint
  capacity, cache price or prompt schedule is inferred.
- **Arcee AI:** five exact Platform model IDs, with separately validated USD/1M
  input/output/cache-read columns. An Arcee offer is not a creator-direct price.
- **Perplexity API:** five default Agent API identities. Orchestrator is private
  preview and stays native-only. Sonar's Agent API identity is separate from
  legacy search endpoints and request fees; optional tools remain outside token
  estimates. An advertised Perplexity-hosted prefix identifies the serving source.
- **Upstage:** two exact dated Solar 4 releases. Model-document token prices and
  the API pricing page's explicit USD setting must both remain valid. Older ended
  service, prepaid bonuses, taxes, Studio plans and introductory history are not
  substituted for the current quotes.

Weight access was not independently reviewed for these 66 identities. Their
`open_weight: null` values display **Weights unverified** in Compare and Models.
Existing verified open/proprietary classifications are unchanged. Observation
dates do not establish release dates or a license.

One retained Vercel DeepSeek V4 Pro 0813 base quote has a scheduled multiplier
whose application is outside the reviewed token interpretation. Its amounts,
ID and prior observations remain unchanged. `pricing_scope_unverified: true`
excludes it from estimates, cheapest-price results, comparable chart series and workload-map winners in
both scenarios. CSVs expose `pricing_scope_verified: false` with blank estimates.
No multiplier, cache treatment, current period or historical period is inferred.
The exact-observation table and append-only dataset retain the original base observations.
The quote stays quarantined until a separate scope review, even if the modifier
later disappears from a response. New unsupported gateway components also fail
comparison eligibility while their native evidence remains available.

## Added public source groups

Each source has a bounded scope. Native records remain
`comparison_eligible: false`, including evidence linked to reviewed identities.

| Source group | Official source | Boundary |
| --- | --- | --- |
| Cohere | [Model directory](https://docs.cohere.com/docs/models.md), [pricing](https://cohere.com/pricing) | Exact model/status evidence and pricing-page context. A pricing-card label does not establish a versioned API quote; instance/search billing remains separate. |
| AI21 | [Jamba models](https://docs.ai21.com/docs/jamba-foundation-models.md), [pricing](https://www.ai21.com/pricing/) | Versioned model directory and Mini/Large price-card context. Generic card labels do not authorize version-specific prices. |
| Perplexity API | [Billing](https://docs.perplexity.ai/docs/getting-started/pricing.md), [Agent models](https://docs.perplexity.ai/docs/agent-api/models.md), [Orchestrator](https://docs.perplexity.ai/docs/router/models.md) | Separate Agent, private-preview Orchestrator, request/tool/session, embedding and decision billing. |
| Cerebras | [Public models](https://api.cerebras.ai/public/v1/models), [format semantics](https://inference-docs.cerebras.ai/api-reference/models/public-models.md) | Complete default public feed and selected model references; Shared/Dedicated and free/paid limits stay distinct. |
| Castform | [Public pricing](https://api.castform.com/v1/pricing) | Inference and training are separate products, including explicitly unpriced training entries. |
| Arcee AI | [API prices](https://docs.arcee.ai/get-started/pricing.md) | Exact Platform identifiers and rates; no inferred upstream bill. |
| StepFun | [Global pricing](https://platform.stepfun.ai/docs/en/guides/pricing/details.md) | Native text, image, audio, voice/session rules and future schedules. Chinese billing and coding subscriptions stay separate. |
| Upstage | [API prices](https://www.upstage.ai/pricing/api), [models](https://console.upstage.ai/docs/models.md) | Current Solar versions, ended service and document products remain distinct; no credit-bonus conversion. |
| Telnyx Inference | [API prices](https://telnyx.com/pricing/inference-api) | Separate deployment/promotional sections and cache expressions; no cheapest-row selection or invented endpoint IDs. |
| TypeSafe | [Models](https://docs.typesafe.ai/models.md) | Typed decisions, input-only billing, explicitly free outputs, and separate per-request/per-question limits. Not generic chat quotes. |
| Black Forest Labs | [FLUX pricing](https://docs.bfl.ai/quick_start/pricing.md) | Native image/resolution/component pricing; no text-token conversion. |
| Runway | [Developer pricing](https://docs.dev.runwayml.com/guides/pricing.md) | Native credits, seconds, images and characters, including hosted models. Consumer allowances are separate. |
| Stability AI | [API pricing](https://platform.stability.ai/pricing) | Credit-priced image/audio/3D/editing services. Published conversion prose does not create reviewed money/token quotes. |
| Ideogram | [API overview](https://developer.ideogram.ai/ideogram-api/api-overview) | API model/capability evidence and linked billing; image modes and consumer credits stay separate. |
| ElevenLabs | [API pricing](https://elevenlabs.io/pricing/api), [models](https://elevenlabs.io/docs/overview/models.md), [billing](https://elevenlabs.io/docs/overview/administration/billing.md) | Model and plan evidence, allowances, characters/tokens/time, minimum purchases and concurrency; no universal flat rate. |
| BytePlus ModelArk | [International tariff](https://docs.byteplus.com/docs/en/modelark/model-pricing.md) | Dated IDs, Standard/Flex, prompt bands, peak schedules, storage hours and non-token services; no Chinese-region equivalence. |
| Adobe Firefly API | [Developer guide](https://developer.adobe.com/firefly-services/docs/firefly-api/guides/) | Limited API product/model documentation; monetary tariffs and consumer-plan equivalence remain unverified. |
| Baidu Qianfan | [Product/model overview](https://cloud.baidu.com/product/wenxinworkshop.html) | Limited public product scope; tariffs, currency, endpoint availability and full-catalog completeness remain unverified. |

New document readers retain original table expressions and bounded normalized
surrounding prose, including access rules, dates, schedules, rounding and plan
conditions. They omit executable markup and fenced SDK/request/response examples.
Document-cell currencies, denominators and current applicability remain unparsed;
an empty structured `rates` list means unknown/unparsed, not free. Public price
feeds have independent schema/unit validation. Raw transport responses remain
transient; the app receives only the existing validated native field allowlist.

## Preservation, verification and remaining limits

Original reviewed identities, offering IDs, observations, CSV bytes and immutable
assets are preserved. Current collector changes append native observations and
bounded immutable segments; original segments are not rewritten. Normalization
corrections for new document sources retain earlier observations and do not assert
vendor price changes. New offers start at actual collection time. The gateway
refresh observed genuine existing-offering quote updates independently of the
100 new offers. Reconciliation with a later production collection preserves both
reviewed observation sets; a further strict gateway refresh adds its actual
newly observed changes without overwriting earlier rates. Parallel native
collection ID collisions retain a complete checksummed branch archive, as
described in [history reconciliation](native-history-compaction.md#parallel-collection-reconciliation).

Live provider-scoped strict dry-runs and legitimate strict collections cover the
18 new groups and two expanded gateways. Other existing providers were not
recollected; this is not a hosted full 47-group collection. Regression fixtures
record exact official-source capture/fixture hashes and distinguish bounded API
selections from complete production catalogs.

Older IDs without a current exact billing witness, ambiguous served versions,
unknown creator/direct-host relationships, unsupported conditional pricing and
consumer subscriptions remain unresolved or native-only. Source absence is not
retirement. Broader collection does not make every model comparable, establish
account access, resume Together or authorize a code release.
