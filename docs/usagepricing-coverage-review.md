# UsagePricing coverage review — 2026-11-04

The requested comparison found three missing direct billing sources and substantial
reviewed-model gaps. Mistral API, Meta Model API and Moonshot AI now join collection.
The official-source review adds **58 canonical identities and 84 first-observed
offerings**, bringing retained coverage to **103 models / 347 offerings / 29
provider groups**. Together remains paused. These are retained identities, not
counts of currently accessible endpoints or unique native models.

## Comparison and remaining gaps

The independently fetched [UsagePricing tracker](https://www.usagepricing.com/ai-token-pricing)
contained **146 entries across 14 provider labels: 127 active and 19 deprecated**.
Its Astro initial data includes hidden retired entries. The cached search view
showed an older 141-entry snapshot. The [complete dated audit](research/usagepricing-gap-review-2026-11-04.json)
retains retrieval time, response hash, every label/status, exact native witnesses
and before/after reviewed offering IDs. Competitor prices and descriptions are
not imported into production data, aliases or historical evidence.

| Disposition in the dated audit | Entries |
| --- | ---: |
| Exact reviewed billing-source coverage after this review | 84 |
| Not found in the selected current billing source | 17 |
| Competitor-retired reference | 19 |
| Creator label without a direct billing quote | 2 |
| Version/served-identity unresolved | 4 |
| Together operator pause | 8 |
| Native evidence awaiting a separate source review | 4 |
| Zhipu label requiring billing-source confirmation | 8 |

The categories account for all 146 entries, without converting billing-source
rows into a unique-model count. These remaining limits stay explicit:

- Older OpenAI rows, Gemini 3.5/3.7 Flash, Kimi K2.5, Groq Qwen 3.6 and selected
  old Fireworks rows lack an exact witness in the selected current source. Absence
  is not discontinuation; a competitor-retained price is not a current official quote.
- Unqualified DeepSeek V4 Pro rows do not establish the separately reviewed 0813
  served identity. Gemini's unqualified 3.1 Pro label does not establish a stable
  identity equivalent to the collected Preview product.
- DeepInfra/Fireworks V4 Flash and Fireworks K3/GLM-5.2 remain native until their
  exact served identity/billing scope is separately verified. The credential-dependent
  Fireworks catalog is preserved; no missing-key fallback replaced it in this review.
- Meta's two Llama 4 rows label the creator, without establishing direct Meta
  Model API billing. Reviewed independent-host quotes already exist. UsagePricing's
  Zhipu label does not identify international versus Chinese billing; related
  international Z.ai coverage exists without inferring Chinese prices.
- Together's eight rows do not override the operator pause or authorize deposits,
  API spending or resumption. A competitor retirement label is not authoritative
  provider lifecycle evidence.

## Primary-source additions

| Source | New identities | New offerings | Reviewed scope |
| --- | ---: | ---: | --- |
| OpenAI API | 21 | 28 | [Standard prices](https://developers.openai.com/api/docs/pricing.md): GPT-6.1 Terra, GPT-5.x/Pro/mini/nano, GPT-4.1/mini, GPT-4o/mini, o3/pro. Both 272K bands where published; current 30-minute writes only. |
| Anthropic API | 7 | 7 | [Direct prices](https://platform.claude.com/docs/en/about-claude/pricing.md): Sonnet 4.5/5, Opus 4.5/4.7/4.8/5, Mythos 5. Exact pricing labels, unverified endpoint strings/capacities, five-minute writes and limited Mythos access. |
| Gemini Developer API | 6 | 7 | [Paid prices](https://ai.google.dev/gemini-api/docs/pricing.md.txt): Argon, 3.6 Flash, 3.1 Flash-Lite, 2.5 Pro/Flash/Flash-Lite. Standard text, Pro bands and dated introductory schedules; audio/storage excluded. |
| Alibaba Model Studio | 5 | 16 | [Singapore/International tables](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/model-pricing.md): all eight Qwen rows. Three Qwen3.8 identities already existed. Preserve all prompt bands, thinking/non-thinking columns and Qwen3.7 Plus's published limited-time 20% discount, with unknown end date. |
| Meta Model API | 4 | 4 | [Standard mode](https://dev.meta.ai/docs/pricing-rate-limits.md): Spark 1.1/1.2/1.3 and Wonder 1.0. Contributor-mode permission/discounts and Muse Code subscriptions are separate. |
| Mistral API | 6 | 6 | [Current pricing](https://docs.mistral.ai/inference/pricing.md): Large 4, Small 4, Ministral 3 3B/8B/14B and Codestral 2508. HTML controls establish USD/Standard; official model references establish exact IDs and weight licenses. Unknown cache prices remain unknown. |
| Moonshot AI | 1 | 3 | [Kimi prices](https://platform.kimi.ai/docs/pricing/chat): K3, K2.7 Code and K2.6; the first two identities already existed. Preserve 5m/1h writes and K2's new-user access restriction from October 31, 2026. Planned end-of-December retirement is not marked completed. |
| xAI | 4 | 8 | [Text prices](https://docs.x.ai/developers/pricing): Grok 4.3/4.5/4.6 and Build 0.1, each with complete `<200,000` / `≥200,000` prompt schedules. |
| Z.ai international | 4 | 4 | [USD tables](https://docs.z.ai/guides/overview/pricing.md): GLM-5/5.1/5.2/4.7. No Chinese billing, subscription or storage-price substitution. |
| DeepInfra | 0 | 1 | [Public catalog](https://api.deepinfra.com/models/list): exact `Qwen/Qwen3.7-Max`, published precision/capacity and cents-per-token conversion. |

Original aliases/source bindings remain intact. Qwen thinking modes share an
endpoint and bands, so their new IDs also distinguish billing mode. No original
offering ID changes. Weight metadata preserves published license terms; it does
not grant unrestricted licensing or inference access. Codestral's unversioned
competitor label does not establish its context limit; only the current official
`codestral-2508` quote is selected.

## Formats, verification and preservation

Google now returns Markdoc tables/tabs. An inert text reader restores explicit
cell boundaries/headings for reviewed and native readers, preserving original
response hashes. Malformed tables fail closed. This layout change produced native
catalog events, not inferred launches, retirements or economic price observations.

Kimi's Markdown omits its custom tables. A bounded grammar reads serialized
`DocTable` literals in the public HTML without executing JavaScript/MDX. Native
evidence retains all six rows, including unreviewed Highspeed/K3.1 variants, and
billing/access prose. New columns, malformed rates, missing tables, changed
capacities or changed K2 access conditions require review. No inference calls run.

Public regression fixtures and parent/excerpt hashes are in
`tests/fixtures/usagepricing-review/manifest.json`. Tests cover every new canonical
identity, exact permissions, thinking-mode IDs, prompt bands, discounts, cache
TTL/mode selection, Markdoc integrity, Kimi literals, native isolation and last-good
retention. October fixtures retain their original explicit review scope and
unchanged economic assertions.

Live strict dry-runs and legitimate local strict collections passed for all ten
affected sources. Other providers were not recollected; this is not a hosted full
29-provider run. DeepInfra also observed three genuine existing-offering price
updates, separately from its one new quote.

All 263 original offering IDs and all 376 original reviewed JSON observations
remain. The original CSV is an identical prefix, all 60 pre-existing immutable
archive/history assets are byte-identical, and original ordered native history
segments are unchanged. Collection appended new segments and advanced the
manifest. New quotes start at actual collection time. No historical archive,
Pages gate, paid recovery setting or deployment changed. Historical recovery
remains scoped to the original **26 groups**, without implied imports for the
three new groups, backfills or invented release dates.
