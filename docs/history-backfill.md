# Historical offering backfill: source coverage and research plan

Research date: **2026-10-25, America/Los_Angeles**. Network probes ran on
2026-10-26 UTC while it was still October 25 locally. This is a research result
and proposed import design, not an implemented backfill or a public coverage claim.

Subsequent implementation: the [historical evidence ledger](historical-evidence-ledger.md)
now retains the selected public AWS/DeepInfra evidence separately from live history.
This document remains the dated discovery research; its proposal sections are not
the ledger's current schema specification.

The agreed discovery scope is all **26 currently indexed billing/source groups**,
including historical-only models, retired SKUs, older routes and unknown prices.
Today's reviewed identities and today's catalogs must not define the historical
search universe. There is no universal starting-year cutoff: follow each source's
available history and report its gaps. Regional/product boundaries remain those in
[pricing sources](pricing-sources.md) and [source scopes](collection-expansion.md).

The [2026-10-26 AWS/DeepInfra follow-up](aws-deepinfra-history-research.md) goes
beyond this initial map: all advertised AWS versions in the selected region,
all returned DeepInfra API captures and the two selected page URLs' pre-API
captures were replayed. It recovers additional historical-only identities and
numeric evidence without importing production history.

## Findings and evidence levels

The [machine-readable research artifact](research/history-backfill-2026-10-25.json)
records exact archive queries, retrieval timestamps, response hashes/bytes, failed
attempts and retries, AWS version pointers and 11 sample extracts. It contains no
production observations and is not an input to collectors, charts or public assets.

- **24 of 26 seed URLs returned archive index entries.** This is URL discovery,
  not 24 validated historical price catalogs. The other two returned empty indexes.
- **DeepInfra replay validated:** the 2024-06-18 public catalog returns 155 native
  records across modalities. Its replay SHA-1 matches the CDX content digest; its
  exact replay SHA-256 is recorded. Four token-priced IDs were sampled.
- **AWS historical file retrieved:** the 2023-09-28 Bedrock version's US East
  (N. Virginia) file contains 20 products; five on-demand token SKUs were sampled.
  The public service indexes returned 37 Bedrock versions and three Foundation
  Models versions. Version counts are dated findings, not price-change counts.
- **Official retrospective/announcement evidence:** OpenAI's deprecation table
  supplies an older exact ID and price; Google's dated Gemini announcement supplies
  an exact ID, token prices, prompt condition and a separate billing-start date.

These are different evidence levels. An indexed capture can be unavailable,
incomplete, an error body or a script shell. A retrospectively reported price is
not a contemporaneous observation. A replayed complete JSON array establishes
the returned capture's contents, not account-independent market completeness.

## All-provider coverage map

Each row below probes **one exact seed URL**, recorded in the JSON artifact. CDX
URL matching can normalize URLs; these are not exhaustive domain searches. The
query requests HTTP-200 entries without digest collapse, at most 5,001 entries and
2 MiB, with a 30-second timeout and at most two concurrent requests. No result hit
the entry cap. Six initial connection failures succeeded on one bounded retry;
their failed attempts remain recorded. No price-body replay was attempted for
the other 25 seeds. The AWS historical price file is a separate official retrieval.

Dates are the earliest/latest **returned index timestamps, in UTC**, not a
continuous coverage interval, launch date, price validity or provider-wide bounds.
The oldest Snowflake PDF entry predates Cortex and does not prove Cortex pricing
existed then. Ended URL ranges often indicate a documentation move, not retirement.

| Provider ID | Index captures | Returned date span (UTC) | Historical route and next coverage check |
| --- | ---: | --- | --- |
| `alibaba` | 38 | 2026-01-16 → 2026-10-19 | Archived Model Studio pricing; expand to older official URL names. Preserve regional tabs, currency, API IDs and prompt bands; do not equate international and China tariffs. |
| `anthropic` | 27 | 2025-05-12 → 2025-09-16 | Old pricing-document URL plus [model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations). Follow the move to Claude Platform; retirement dates are platform-specific. |
| `azure` | 0 | None returned | Exact current Foundry/East US query has no index entries. [Retail API documentation](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) does not establish complete superseded-price retrieval. Research former Azure OpenAI names, historical documents and meter IDs. |
| `bedrock` | 1,347 | 2023-09-29 → 2026-10-24 | Official [service-version indexes](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-the-aws-price-list-bulk-api-fetching-price-list-files-manually.html) are preferable to page archives; walk both Bedrock services, retaining US East scope and exact SKU/rate codes. |
| `cloudflare` | 101 | 2024-03-01 → 2026-10-26 | Archived pricing and [2025-02-20 billing-rule update](https://developers.cloudflare.com/changelog/post/2025-02-20-updated-pricing-docs/). Historical bucket pricing and later per-model mappings need distinct rules; retain neurons. |
| `databricks` | 28 | 2024-04-15 → 2026-08-29 | Archived open-model prices, separate proprietary-model page and [retirement tables](https://docs.databricks.com/aws/en/machine-learning/retired-models-policy). Keep DBUs, serving modes and cloud scope; retirement alone supplies no old price. |
| `deepinfra` | 31 | 2024-06-18 → 2026-10-19 | Public models API capture successfully replayed. Extract all historical returned IDs, not only reviewed families; research native cents currency and lifecycle-field contracts before conversion. |
| `deepseek` | 292 | 2024-11-07 → 2026-10-26 | Archived models/pricing plus official announcements. Preserve served versions, cache definitions, promotions and scheduled rates; older tables require historical parsers. |
| `fireworks` | 18 | 2026-05-07 → 2026-10-16 | Current document path has short coverage; expand older pricing paths and [March 2024 announcement](https://fireworks.ai/blog/dedicated-deployments-postpaid-billing-update). Historical flat-token and split-direction billing are distinct. No authenticated archive requests. |
| `gemini` | 209 | 2023-12-13 → 2025-02-16 | Seed is the old `ai.google.dev/pricing` path; follow its successor plus dated developer announcements. Separate Developer API from Vertex, paid/free scope and experimental/stable IDs. |
| `groq` | 233 | 2024-03-01 → 2026-10-25 | Archived model tables plus [April 2024 Llama 3 announcement](https://groq.com/blog/12-hours-later-groq-is-running-llama-3-instruct-8-70b-by-meta-ai-on-its-lpu-inference-enginge). Reconcile display names to exact historical IDs, without guessing. |
| `huggingface` | 47 | 2025-04-01 → 2026-10-12 | Archived billing guide, router catalogs and [January 2025 provider integration announcement](https://huggingface.co/blog/inference-providers). A guide capture need not contain route prices; provider routes and compute seconds remain separate. |
| `minimax` | 37 | 2026-02-13 → 2026-10-11 | Archived international PAYG page plus [model release notes](https://platform.minimax.io/docs/release-notes/models). Current page redirects to pricing overview; search former paths and preserve promotions/bands. Token Plans are separate. |
| `nebius` | 7 | 2025-04-04 → 2025-10-17 | Old AI Studio page is a seed for the Token Factory URL transition. Probe historical public catalogs next; verify product continuity and retain flavors/regions, not changing performance measurements. |
| `novita` | 1 | 2025-02-17 → 2025-02-17 | One indexed API capture; replay remains unchecked. [Dated changelog](https://docs.novita.ai/changelog) provides additional old IDs/deprecations. Expand pricing/model-page URLs. |
| `openai` | 123 | 2023-02-09 → 2026-02-07 | Former platform pricing URL plus [deprecation tables](https://developers.openai.com/api/docs/deprecations). Old exact IDs/prices are directly recoverable; retain unqualified token billing and unknown historical cache retention. |
| `openrouter` | 232 | 2023-07-26 → 2026-10-25 | Public models API has a long indexed range; replay/catalog validation is next. Preserve gateway IDs, dynamic-price sentinels and pricing units; no inferred supplier endpoint price. |
| `oracle` | 0 | None returned | Exact pricing-page seed returned no entries. [On-demand retirement table](https://docs.oracle.com/en-us/iaas/Content/generative-ai/deprecating-on-demand.htm) recovers old IDs; investigate older price-list URLs and exact part-number links separately. |
| `ovhcloud` | 55 | 2025-11-07 → 2026-10-11 | Archived commercial catalog plus [2024 alpha announcement](https://corporate.ovhcloud.com/en/newsroom/news/ai-endpoints-alpha/). Search former lab/catalog URLs; do not use a page's EUR price to silently resolve another API record's unknown currency. |
| `scaleway` | 31 | 2025-01-30 → 2026-10-22 | Archived model-as-a-service pricing and public product-catalog SKUs. Probe historical API captures; retain EUR, locality, mode and native unit. |
| `snowflake` | 81 | 2021-04-24 → 2026-10-12 | Archived consumption-table PDF plus [Cortex availability/lifecycle](https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql-regional-availability). Determine first AI-bearing edition; page text alone does not align model/rate columns. Preserve credit type. |
| `together` | 234 | 2023-07-14 → 2026-10-25 | Free pricing archives and [July 2024 Turbo/Lite announcement](https://www.together.ai/blog/together-inference-engine-2). Distinct endpoint variants remain distinct; current comparisons stay paused and the deposit-gated API stays unused. |
| `vercel` | 42 | 2025-06-28 → 2026-10-20 | Archived gateway pricing guide/catalog and dated changelog. Guide captures do not guarantee model prices; gateway launch scope, tiers and time-limited discounts need separate evidence. |
| `vertex` | 189 | 2024-03-10 → 2026-04-22 | Archived pricing plus [bounded historical Cloud Billing queries](https://docs.cloud.google.com/billing/docs/reference/rest/v1/services.skus/list). Historical API retrieval not performed; enumerate monthly windows and retain request bounds. |
| `xai` | 79 | 2025-01-21 → 2026-02-04 | Former model-doc URL plus [release notes](https://docs.x.ai/developers/release-notes), which mention older beta and dated IDs. Expand predecessor paths; model alias retargeting is not automatically a tariff change. |
| `zai` | 90 | 2025-07-28 → 2026-10-25 | Archived international pricing plus [release notes](https://docs.z.ai/release-notes/new-released). International API, Chinese Zhipu and Coding Plan billing stay separate. |

Exact seed queries and results are in the research artifact; current official
collection endpoints remain listed in the existing source guides. No absence at
one URL establishes historical absence. The next discovery pass must cover URL
predecessors, redirects, HTML/Markdown variants, model-detail pages and public
documentation repositories where available. Git commit dates establish document
revision provenance, not necessarily tariff-effective times.

## Recovered sample offerings

All 11 samples are research-only and `comparison_eligible: false`. They demonstrate
recovery methods, not a complete provider history or a current availability claim.
Exact fields and source-body hashes are in the research artifact. Raw downloads
remain temporary: the extracts are not a substitute for the durable evidence
retention needed before a real import.

### Official historical billing file: five AWS SKUs

The [2023-09-28 US East Bedrock file](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/20230928150907/us-east-1/index.json)
publishes these USD amounts per **1K tokens**, on-demand, range `0` to `Inf`:

| Native SKU | Published product/direction | USD / 1K tokens |
| --- | --- | ---: |
| `9XHSKPBV6R8E4FUY` | Titan Text G1 Lite input | 0.0003000000 |
| `RBJWS42PM5UET2HZ` | Titan Text G1 Lite output | 0.0004000000 |
| `WK92UTYU8723FP82` | Titan Text G1 Express input | 0.0013000000 |
| `GSRHBBD5A5TVQ7CC` | Titan Text G1 Express output | 0.0017000000 |
| `RS4JPUWRVXVJCUCE` | Titan Embeddings G1 Text input | 0.0001000000 |

The file's publication is `2023-09-28T15:09:07Z`; these terms state
`2023-09-28T00:00:00Z`. Neither is our collection time. Preserve billing SKUs,
usage types and rate codes; the embedding input is not a generative output quote.

### Replayed native catalog: four DeepInfra IDs

The [2024-06-18 16:54:58 UTC replay](https://web.archive.org/web/20240618165458id_/https://api.deepinfra.com/models/list)
contains these exact IDs and native pricing fields:

| Native model ID | Cents / input token | Cents / output token |
| --- | ---: | ---: |
| `meta-llama/Llama-2-7b-chat-hf` | 0.000007 | 0.000007 |
| `meta-llama/Llama-2-70b-chat-hf` | 0.000064 | 0.00008 |
| `meta-llama/Meta-Llama-3-8B-Instruct` | 0.000008 | 0.000008 |
| `mistralai/Mixtral-8x7B-Instruct-v0.1` | 0.000024 | 0.000024 |

The replay uses `cents_per_input_token` / `cents_per_output_token` without a currency
code; this research does not assert a USD conversion. The two Llama 2 entries also
retain native `deprecated` values and `replaced_by` strings. Their presence in a
returned catalog does not prove they were accepting requests. Lifecycle-field
semantics and price-effective dates remain unresolved.

### Retrospective official table: OpenAI

The [deprecation table](https://developers.openai.com/api/docs/deprecations)
lists `gpt-4-32k-0613` at USD 60 input / 120 output per million tokens and reports
shutdown on 2025-06-06 under its 2024-06-06 notice. This recovers an exact old ID
and a reported historical price, without establishing the tariff's start or its
entire validity interval. Retain the separate source/notice/shutdown dates; do not
backdate a new `observed_at` or treat a replacement recommendation as an alias.

### Dated announcement: Gemini Developer API

Google's [2024-10-03 announcement](https://developers.googleblog.com/en/gemini-15-flash-8b-is-now-generally-available-for-use/)
names `gemini-1.5-flash-8b`, input USD 0.0375, output USD 0.15 and cached prompts
USD 0.01 per million tokens for prompts **<128K**. It separately says paid-tier
billing starts October 14. Preserve the strict written boundary, paid-tier
condition and date precision; do not infer a midnight UTC instant, cache-write
rate, Vertex rate or prices outside the stated prompt scope.

## Proposed import representation

Implement a separate retrospective evidence ledger before connecting history to
the app. Do not replay old captures through the current collector's required-model
set or append them as newly discovered daily observations in production history.

| Object | Required evidence and semantics |
| --- | --- |
| Source capture | Original public URL, exact final/archive target, archive capture time, actual retrieval time, source publication time where explicit, content hash/bytes, request bounds/pagination and completeness status. Retain exact source bytes in a separately designed bounded warehouse evidence layout; never copy wholesale into public projections. |
| Extraction | Capture reference, parser/version, source row/JSON pointer, original ID/amount/unit/currency/conditions, supported scope and unresolved fields. A valid old record does not require all today's model IDs. |
| Historical offering | Provider-scoped exact native identity, source namespace, region/tier/mode/bands and evidence references. Unknown identity, rename or alias continuity stays unresolved. Link shared model identity only through separate review. |
| Price assertion | Exact decimal values and original billing expression, capture/reported/effective date basis, precision/timezone, applicability and review status. Unknown prices remain unknown. |
| Lifecycle assertion | Explicit source statement versus observed listing/absence, affected product/platform/scope, announcement date and scheduled/confirmed retirement. Last captured appearance is not an end-of-sale date. |
| Coverage | URLs/windows searched, captures enumerated/replayed/parsed, caps/pagination, gaps/failures and unresolved evidence. A failed chunk/request cannot become a complete empty catalog. |

Use separate date fields: `retrieved_at`, `archive_capture_at`,
`source_published_at`, `source_reported_effective_at`, and explicit precision/basis.
Keep production `observed_at` and existing event IDs unchanged. A price difference
between two captures gives an interval in which a change was observed; a source
must independently establish an exact effective date. Conflicting assertions
coexist with their provenance until resolved, rather than silently overwriting.

Content-addressing can share identical bytes, but **retain ordered capture
references**. Global digest deduplication must not erase A → B → A reversions.
Monthly sampling may prioritize discovery; it is not complete price history and
must not replace inspection of all enumerated distinct states. Request boundaries
and rolling as-of timestamps must not create synthetic monthly tariff changes.

Historical API access needs source-specific validation. Google's range must fit
within one America/Los_Angeles calendar month; preserve all returned pricing
versions and pagination. Its returned effective time is constrained to the request
range, so a boundary timestamp alone cannot establish a new price. Historical
queries also need a separate normalization path from the current unbounded-latest
timestamp optimization. No authenticated historical API call was made in this pass.

Before import, specify exact-byte retention, hashes/ordered manifests, bounded
segments, locking/retries, deterministic extraction and reconstruction tests.
Do not repurpose the immutable compaction archive, rewrite existing history or
require a database, paid archive/storage, new credentials or inference requests.
Public display would need a separate validated projection and schema/UI change;
the existing public native allowlist is unchanged by this research.

## Recommended implementation sequence

1. **Build discovery and staging across all providers.** Expand the 26 seed URL
   histories, use archive pagination/resumption for larger queries, enumerate AWS
   versions and add source-specific lifecycle/announcement discovery. Track
   coverage before extracting prices. Include historical-only IDs with no price.
2. **Prove import mechanics on AWS and DeepInfra**, then OpenRouter and Novita.
   These include official historical SKUs, an already verified archived catalog,
   a gateway and sparse API coverage. Parse every supported returned record,
   including older families; current comparison aliases are not admission rules.
3. **Extend document and lifecycle recovery across all remaining providers.**
   Prioritize older URLs and sources with
   explicit old IDs; reconcile only with two-sided source evidence. This sequencing
   does not narrow final coverage.
4. **Review retrospective evidence and public semantics**, then implement a
   historical offering explorer with explicit gaps/date bases. Keep native history
   and separately curated comparable history distinct. No import or publication
   occurs as part of this research deliverable.

Acceptance for a first import: stable historical identities, exact source evidence,
retained unknowns/non-token billing, explicit temporal basis, ordered reversions,
bounded/retry-safe storage, unchanged existing observations and no promotion into
current calculators. A provider can have successful discovery with no recoverable
price, or recovered prices with incomplete historical coverage.

## Verification and remaining limits

Live work here consisted of public archive-index queries, one archived public API
replay, AWS version-index/historical-file downloads and official-document research.
No production collector, credentialed API, inference request or deployment ran.
Only the selected DeepInfra replay was checked against its CDX content digest;
AWS and document hashes identify downloaded bytes rather than independent archive
verification. Full raw historical bytes are not retained in these research files.

The source map and sample relationships were checked against the committed provider
inventory. All 11 tests in `python3 -m unittest discover -s tests -p test_documentation.py -v`
passed, as did `git diff --check`. Additional read-only checks verified all 26
provider IDs, capture counts/response hashes, six downloaded source witnesses,
the DeepInfra replay digest and all 11 samples' research-only flags/references.
README, the collection guide and AGENTS document the research scope; production
coverage counts, gates, allowlists and behavior are unchanged.
This does not prove complete archives, all price-effective dates, model
currency/identity equivalence or a working historical importer. Existing daily
collection and its meaningful-change retention remain unchanged.
