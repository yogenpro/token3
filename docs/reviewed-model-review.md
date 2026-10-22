# Recent-model comparison review — 2026-10-11

## Scope and resulting data

The requested Opus 5.5, Fable 5/5.1, GPT-6.1 Sol, GPT-6 Luna and GPT-6 Astra now have explicitly reviewed comparison quotes. The same review selected additional recent/current-generation models already found in the native inventory: Sonnet/Haiku/Mythos 5.x, GPT-6 Sol, Gemini 3.1 Pro Preview, Gemma 4, Qwen3.8, DeepSeek V4.1 Flash / V4 Pro 0813, GLM-5.3 variants, MiniMax M3, Kimi K3 / K2.7 Code, Nemotron 3/3.5, Llama 4 and Grok 4.7.

This added **33 canonical identities and 145 first-observed offerings**, bringing retained reviewed coverage to **45 models / 216 offerings / 12 billing providers**. The complete model/provider matrix is in [README](../README.md#reviewed-coverage-and-collection-scope). There were 214 active offerings in this local observation; active counts are not permanent scope guarantees. Existing inactive Novita offerings remain retained.

“Recent/current-generation” is a selected model-family review, not an exhaustive release-date search or a claim that every model is newly launched. Provider listing, native observation, first reviewed observation and vendor release are distinct dates. An advertised model or price does not establish account access, endpoint equivalence, performance or continued availability.

## Identity and permission are separate

`catalog/models.yaml` defines exact canonical versions. `catalog/aliases.yaml` declares identity aliases and, for every new entry, `reviewed_sources` containing **provider IDs mapped to exact source model IDs**. `ReviewedAliases.for_provider()` passes only that provider's approved new IDs to its collector; normalization checks the same permission before accepting a quote.

Historical alias/collector behavior remains unchanged for the original 12 models and 11 providers. New source bindings do not automatically enroll an identity on another provider. The same model may be recognized in a native catalog without its native price becoming a reviewed quote.

Examples of deliberate separation:

- `gpt-6.1-sol`, `gpt-6-sol`, `gpt-6-luna` and `gpt-6-astra` are distinct. No `gpt-6.1-luna` alias was invented.
- Fable 5, Fable 5.1, Mythos 5.1, Opus 5.5, Sonnet 5.5 and Haiku 5.5 are distinct, even when prices happen to coincide.
- Dated DeepSeek V4 Pro 0813 is not silently equated with a mutable V4 Pro ID.
- Qwen3.8 Max is not Max-0902, Max Prime or Omni Flash. Provider Fast/Highspeed/Decisions/suffix variants are not stripped into an alias.
- Llama Maverick/Scout and Gemma sizes remain distinct. Explicit FP8/BF16/Turbo offerings retain their own source IDs and published precision; unknown precision is not fabricated.
- Open-weight labels concern published weights, not an unrestricted/open-source license claim. Publisher repositories can require custom terms or gated access. Model prices do not grant weight or inference access.

## Primary pricing evidence and billing review

| Billing source | Primary evidence | Reviewed interpretation |
| --- | --- | --- |
| OpenAI API | [Official pricing Markdown](https://developers.openai.com/api/docs/pricing.md) | Standard USD per million text tokens, including exact cache read/write columns. Full-prompt short/long boundary is 272,000/272,001. The new four GPT-6 identities require both bands; missing long rates fail rather than extrapolate the cheaper short price. Batch/Fast/Pro and ChatGPT subscriptions are separate. New endpoint context/output capacities remain unverified. |
| Anthropic API | [Official pricing Markdown](https://platform.claude.com/docs/en/about-claude/pricing.md) | First-party global base input/output, cache reads and five-minute writes. One-hour writes and Batch are not mixed in. Haiku 5.5 requires both <=100,000 and >100,000 full-prompt schedules. Fable 5.1/Mythos 5.1 and Opus/Sonnet 5.5 use their actual cache prices, not an older model's multiplier. Mythos remains limited availability. |
| Gemini Developer API | [Official paid pricing](https://ai.google.dev/gemini-api/docs/pricing.md.txt) | Pro 3.1 Preview Standard rates have <=200,000 and >200,000 prompt bands. Its Batch table is not called Flex. The token-hour cache-storage charge is excluded from cache-read rates. Customtools/Omni/other previews are not aliases; Preview endpoint capacity/output limits remain unverified. Existing stable Gemini tier/date schedules are preserved. |
| DeepInfra | [Public model API](https://api.deepinfra.com/models/list) | Explicit cents/token × 10,000 to USD/1M, published cache/tier multipliers and actual endpoint precision/context. Selected flat token-priced identities only; unknown price tables are rejected, not guessed. |
| Novita | [Public model API](https://api.novita.ai/v3/openai/models) | Explicit USD `price_per_m_decimal` fields, including newly reviewed cache-read components. Integer billing fields are not USD. MiniMax M3's unsupported tiered billing is deliberately not enrolled here. |
| Groq | [Official model document](https://console.groq.com/docs/models.md) | Exact Qwen3.8 27B ID, published USD/1M input/output and context. Missing that newly required public quote fails closed; historical Contact Sales rows remain excluded. |
| Vercel AI Gateway | [Public models API](https://ai-gateway.vercel.sh/v1/models), [REST field/range semantics](https://vercel.com/docs/ai-gateway/sdks-and-apis/rest-api), [service-tier semantics](https://vercel.com/docs/ai-gateway/models-and-providers/service-tiers), [billing guide](https://vercel.com/docs/ai-gateway/pricing) | Separately curated **gateway billing** quotes: USD/token × 1,000,000; integer `[min,max)` ranges become inclusive stored upper bounds `max-1`. Input/output/cache schedules must be contiguous and agree with their base rates. Explicit Standard/Flex/Priority prices remain separate; missing long-context cache rates are not inherited. Gateway/default routing does not identify an upstream supplier or guarantee the tier actually served. |

All compared token rates are USD/1M; native rows retain their original units and remain `comparison_eligible: false`. Tools, cache writes/storage, non-token/modality charges, taxes, credit purchase/account fees, negotiated rates and performance are outside workload estimates. Missing cache rates fall back to regular input cost, not free caching. Unknown limits remain unverified rather than asserted unlimited.

Vercel's Fast, ultrafast, regional and Batch pricing, as well as non-language models and complete original billing rules, remain in the native catalog. Cache-write TTL is not established by that catalog and is labeled unverified rather than assumed equivalent to Anthropic's five-minute TTL. Gateway data is not a substitute for a direct provider's price: newer GPTs also have direct OpenAI quotes, and the requested newer Claudes have direct Anthropic quotes.

## Deliberate remaining gaps

- Newer AWS/Vertex/Foundry records are still native evidence unless their exact billing meters, endpoint region, tier, prompt bands and cache conditions have separately reviewed bindings. This expansion does not change existing cloud scope or transplant first-party prices into cloud quotes.
- OpenRouter remains inventory-only; no supplier endpoint or dynamic routing price was inferred. Vercel review does not enroll another gateway automatically.
- Novita's MiniMax M3 tier table remains unsupported for comparisons; its full evidence is preserved. Other unreviewed source variants and modalities are not silently skipped into an equivalent cheap base model.
- Gemini Omni/customtools variants, other GPT-5.x/Pro products, Qwen Prime/dated/Omni products and other recently discovered families remain available in native exploration pending explicit additional review. This is not proof of nonexistence or discontinuation.
- OVHcloud currency and Snowflake model/rate alignment remain unverified. Native DBUs, credits and other units are not converted to token prices.

## Verification and observation provenance

The seven affected sources passed a provider-scoped **live strict dry-run**. After offline parser/normalization regressions passed, a separate legitimate **local strict collection** recorded 177 current quotes across those seven providers, including 145 new offering identities. This was not a hosted full 26-provider run or a deployment.

Preservation checks against the pre-expansion dataset established:

- All 71 retained original offering IDs and their reviewed price signatures were preserved.
- Original reviewed CSV bytes remained an identical prefix; original JSON history observations remained unchanged. New rows start at real collection time, never a manufactured historical date.
- Native inventory history and the Vertex catalog remained byte-identical; the collection created zero native history events.
- Every pre-existing legacy source archive remained byte-identical. Only ordinary check/freshness metadata advanced for the selected sources.

Bounded public-source excerpts in `tests/fixtures/*-reviewed-expansion.*` and their capture-hash manifest test identity permissions, units, cache components, exact boundaries, complete tracked snapshots, failure retention, stable IDs and unchanged historical scope. They are test inputs, never production backfills. Browser checks exercise the actual generated reviewed dataset while native-only discovery isolation remains enforced.

No inference endpoint, paid API recovery, worker provisioning, Pages gate or deployment was enabled by this review.

### Separately authorized publication

On 2026-10-12 the user separately authorized committing, pushing and deploying the local reviewed expansion and data-fit dashboard. Pages remains a manual, main-only release gated by `ENABLE_PAGES=true`; paid recovery and worker provisioning remain disabled. The deployment builds the exact dispatched commit, not an unpinned later checkout of `main`.

Integration preserves the scheduled collection commit and original reviewed/native history. Local provider-scoped refreshes can validate the seven expanded billing sources without replacing retained credential-dependent native catalogs. A local full-source run using missing-key document fallbacks is not equivalent to the hosted API inventory: retain the last-good API snapshots and use the credentialed hosted collection for final full-source validation. Collector success alone does not establish the same source scope or comparison eligibility.

## OpenAI table and cache-write scope review — 2026-10-22

Issue #3 reproduced a change to the official Standard Markdown table: reordered price columns, explicit 30m/12h write columns, and a separate compact table for GPT-5.4 mini. The fetched body matched the failed run's source SHA-256 `129d6019819379a6f30edc0811d4631ddb085dcd4b3b1d0012a945cd1af1bfbf`. This was not an outage or permission problem, and the last-good reviewed quotes were correctly retained.

The user explicitly approved using **30-minute retention for current labelled OpenAI cache-write quotes**, with 12-hour rates native-only. This is a reviewed current-scope decision, not an assertion that the older unqualified cache-write column established a 30-minute TTL. No historical TTL is backfilled, and matching amounts alone are not treated as proof of historical equivalence.

All 11 existing OpenAI offering IDs, selected amounts, currency, per-million denominator, global/Standard scope, 272,000/272,001 bands and known/unverified capacities remain unchanged. The new quote notes expose the current 30-minute condition; original CSV/JSON observations, provenance and native history are not rewritten. No aliases, canonical models, additional tiers or 12-hour comparison offerings are introduced. Cache-write fees remain outside workload estimates.

The issue fix is verified with immutable legacy fixtures, a new bounded public-source excerpt and a provider-scoped strict dry-run. Actual data/health updates must come from a legitimate complete strict collection after review/merge. Publishing the parser change still requires a separately authorized manual code release; the data-only publishing gate is not permission to deploy new code.
