# Recent-provider historical backfill — 2026-11-05

The user explicitly requested historical research and backfilling for the recent
provider/model additions. This extends the original 26-group historical scope to
the 47 selected groups, independently of current quote review. The two November 4
reviews added 21 source groups and 124 reviewed canonical identities. Historical
evidence remains unreviewed and comparison-ineligible.

## Source choices

Use exact public pricing/model documents and public archive indexes. The selected
URLs are in [the versioned profiles](../config/historical_sources.json), including
older pricing locations where today's URL has no captures. Discovery is bounded
to those URLs; it does not use authenticated endpoints, inference requests, paid
archive services or Together's deposit-gated API.

The new profiles cover Adobe, AI21, Arcee, Baidu, Black Forest Labs, BytePlus,
Castform, Cerebras, Cohere, ElevenLabs, Ideogram, Meta, Mistral, Moonshot,
Perplexity, Runway, Stability, StepFun, Telnyx, TypeSafe and Upstage. The expanded
OpenRouter and Vercel catalogs are also checked for later captures, preserving
gateway billing rather than inferring creator-direct history. The newly reviewed
model bindings also lead to archive checks for seven existing billing groups:
Alibaba, Anthropic, DeepInfra, Gemini, OpenAI, xAI and Z.ai. All indexed captures after October 27 are selected for these seven groups. Previously retained
evidence remains valid independently of when an identity was added to comparisons.

Current Markdown locations often have little archived history. HTML pricing pages
and former documentation paths provide additional evidence. BytePlus retains its
case-sensitive historical `ModelArk` path; an index returned for a differently
cased path is excluded rather than weakening exact-source validation. Castform's
website pricing is separate from its public API. Baidu's former product/billing
paths do not imply that an unpriced product guide contains a tariff.

This pass selects the oldest/newest capture for each source URL and the first
capture in each calendar quarter, plus the available Cerebras public model-feed
captures and later gateway captures not already present in the ledger. Other
successfully recovered bodies from the initial discovery pass are preserved too. Retained
indexes describe additional candidates. Unselected references remain explicitly
deferred or retain their actual failed lookup state; this is sampled evidence, not continuous or exhaustive price history.
Failed transports, ambiguous tables and JavaScript-only shells do not become
successful price recovery. Alternative archives, official repository history and
dated announcements remain possible follow-ups where selected captures cannot
establish model/rate mappings; they have not been imported by implication.

## Import and preservation

Discovery stages sources outside production data. Replay bytes must match their
retained index's timestamp, original URL and SHA-1 digest; SHA-256 binds the exact
source bytes and immutable warehouse assets. Offline preflight and an isolated
dry-run precede the append-only import. Retrieval, archive, publication and
reported-effective dates remain distinct; no current quote is assigned an older
observation date.

The explicit historical publication directory is extended in
[`config/historical_publication.json`](../config/historical_publication.json).
Each group still needs a retained public capture and a current directory entry.
The existing validated, read-only projection publishes only its field allowlist
and bounded chunks. Raw source bytes, warehouse manifests/segments and arbitrary
metadata remain outside the app. This backfill does not authorize a code release.

Current reviewed prices, aliases, observations, CSV rows, native warehouse data
and provider pause policies are preserved. Media credits, native currencies,
training rates, plan allowances, generic model labels and unknown units retain
their own scope; none becomes a reviewed historical comparison.

## Recovered batch and gaps

The validated batch contains **454 captures** (77 archive indexes and 377 archived
bodies), **28,873 assertions** and **1,311 standalone lookup records**. These counts
include repeated source evidence, not 28,873 models or price changes. Two selected
captures still return redirects; their bodies were not imported. Other indexed
references remain deferred or retain their actual transport-failure reports.
Earlier successful evidence is not erased by a later failed or deferred lookup.

The [dated report](research/recent-provider-history-2026-11-05.json) records source
bounds, extraction states, exact-ID examples and preservation checks. The table
below separates structured native prices from conservative document candidates.
Zero candidates does not prove that a source had no prices: amounts or their
units/model associations can remain in unparsed prose or document-local rows.

| Billing source | Archived bodies | Structured native price assertions | Document price candidates | Archive capture span |
| --- | ---: | ---: | ---: | --- |
| [Adobe Firefly API](https://developer.adobe.com/firefly-services/docs/firefly-api/guides/) | 8 | 0 | 0 | 2024-08-14 to 2026-08-10 |
| [AI21](https://www.ai21.com/pricing/) | 29 | 0 | 0 | 2024-04-22 to 2026-11-04 |
| [Arcee AI](https://docs.arcee.ai/get-started/pricing) | 6 | 0 | 0 | 2025-11-18 to 2026-07-15 |
| [Baidu Qianfan](https://cloud.baidu.com/product/wenxinworkshop.html) | 14 | 0 | 0 | 2023-05-26 to 2025-07-08 |
| [Black Forest Labs](https://docs.bfl.ai/quick_start/pricing) | 9 | 0 | 71 | 2025-08-05 to 2026-10-22 |
| [BytePlus ModelArk](https://docs.byteplus.com/docs/en/modelark/model-pricing) | 8 | 0 | 98 | 2026-01-16 to 2026-10-19 |
| [Castform](https://api.castform.com/v1/pricing) | 4 | 0 | 14 | 2026-06-17 to 2026-10-06 |
| [Cerebras](https://api.cerebras.ai/public/v1/models) | 12 | 9 | 0 | 2025-04-15 to 2026-10-21 |
| [Cohere](https://cohere.com/pricing) | 57 | 0 | 0 | 2023-04-21 to 2026-11-04 |
| [ElevenLabs](https://elevenlabs.io/pricing/api) | 31 | 0 | 0 | 2025-03-20 to 2026-11-04 |
| [Ideogram](https://developer.ideogram.ai/ideogram-api/api-overview) | 8 | 0 | 0 | 2025-08-07 to 2026-10-08 |
| [Meta Model API](https://dev.meta.ai/docs/pricing-rate-limits) | 10 | 0 | 29 | 2026-08-04 to 2026-11-03 |
| [Mistral API](https://docs.mistral.ai/inference/pricing) | 18 | 0 | 2 | 2025-03-21 to 2026-11-04 |
| [Moonshot AI](https://platform.kimi.ai/docs/pricing/chat) | 12 | 0 | 0 | 2025-06-17 to 2026-10-26 |
| [Perplexity API](https://docs.perplexity.ai/docs/getting-started/pricing) | 15 | 0 | 287 | 2024-09-13 to 2026-11-05 |
| [Runway](https://docs.dev.runwayml.com/guides/pricing/) | 10 | 0 | 397 | 2025-07-15 to 2026-10-23 |
| [Stability AI](https://platform.stability.ai/pricing) | 15 | 0 | 0 | 2023-07-27 to 2026-09-11 |
| [StepFun](https://platform.stepfun.ai/docs/en/guides/pricing/details) | 8 | 0 | 103 | 2026-04-07 to 2026-10-21 |
| [Telnyx Inference](https://telnyx.com/pricing/inference-api) | 12 | 0 | 20 | 2023-10-01 to 2026-10-22 |
| [TypeSafe](https://docs.typesafe.ai/models) | 6 | 0 | 0 | 2026-09-17 to 2026-11-03 |
| [Upstage](https://www.upstage.ai/pricing/api) | 13 | 0 | 0 | 2025-06-19 to 2026-10-11 |
| [OpenRouter](https://openrouter.ai/api/v1/models) | 13 | 5117 | 0 | 2023-07-26 to 2026-11-03 |
| [Vercel AI Gateway](https://vercel.com/docs/ai-gateway/pricing) | 9 | 2244 | 12 | 2025-06-28 to 2026-11-04 |
| [Alibaba Cloud Model Studio](https://www.alibabacloud.com/help/en/model-studio/model-pricing) | 1 | 0 | 510 | 2026-10-28 to 2026-10-28 |
| [Anthropic API](https://docs.anthropic.com/en/docs/about-claude/pricing) | 11 | 0 | 138 | 2026-10-28 to 2026-11-04 |
| [DeepInfra](https://api.deepinfra.com/models/list) | 3 | 0 | 504 | 2026-11-02 to 2026-11-04 |
| [Google Gemini API](https://ai.google.dev/pricing) | 9 | 0 | 2696 | 2026-10-28 to 2026-11-02 |
| [OpenAI API](https://platform.openai.com/docs/pricing) | 16 | 0 | 335 | 2026-10-28 to 2026-11-04 |
| [xAI](https://docs.x.ai/docs/models) | 6 | 0 | 33 | 2026-10-28 to 2026-11-03 |
| [Z.ai](https://docs.z.ai/guides/overview/pricing) | 4 | 0 | 32 | 2026-10-31 to 2026-11-04 |

Of the 124 recently added canonical identities, **61 already had exact
provider/native-ID matches** in the original corpus. Added evidence supplies
**13 more**. Another **50 have no exact native-ID match** under the bindings from
the two November 4 review manifests; document labels or narrative may still
mention them. This diagnostic does not create historical aliases, verify a
model-to-price mapping, or establish absence. The report retains examples and
keeps unknown mappings explicit.

The original 69 historical manifest segments remain an unchanged ordered prefix.
Checksums cover 133 existing live-data, catalog and pause-policy files. Current
reviewed prices, original observations and native warehouse history are unchanged.

## Reproduce the workflow

```bash
python -m scripts.discover_historical_evidence \
  --stage-dir /tmp/token3-recent-history --provider mistral --max-requests 100
python -m scripts.prepare_historical_discovery \
  --stage-dir /tmp/token3-recent-history
python -m scripts.import_historical_evidence \
  --input /tmp/token3-recent-history/validated-sources.json \
  --checks /tmp/token3-recent-history/validated-checks.json --dry-run
python -m scripts.import_historical_evidence \
  --input /tmp/token3-recent-history/validated-sources.json \
  --checks /tmp/token3-recent-history/validated-checks.json --apply
python -m scripts.historical_ledger verify
```

Use the project's Python environment. Discovery makes bounded public requests;
preflight, preview, import and verification are offline. The general discovery
command can process all indexed entries within its request/byte budget; the
quarterly selection above describes this dated research pass, not a new automatic
sampling rule or a scheduled collector.
