# AWS and DeepInfra historical recovery

Research date: **2026-10-26**. This extends the
[all-provider discovery map](history-backfill.md). Production catalogs, observations,
aliases and public assets are unchanged. The results below are recovered evidence
and difference candidates, not imported history or newly reviewed comparisons.

Subsequent implementation: the [historical evidence ledger](historical-evidence-ledger.md)
now durably retains these public source bytes and reconstructed native assertions.
The temporary-storage statements below describe the preceding research phase;
the ledger guide defines the current storage and commands. Live observations and
public comparisons remain unchanged.

## How far the sources reach

| Source | Successfully inspected | Recovered identities | Earliest useful evidence |
| --- | --- | --- | --- |
| AWS `AmazonBedrock`, US East (N. Virginia) | All 37 versions returned by the refreshed service index | 1,089 distinct billing SKUs | Version beginning 2023-09-28; historical file published that day |
| AWS `AmazonBedrockFoundationModels`, same region | All three returned versions | 702 distinct billing SKUs | Index reports a first version beginning 2024-04-01; that file was published in November 2025, not captured in April 2024 |
| DeepInfra public models API | All 31 returned exact-URL archive captures, 2024-06-18 through 2026-10-19 | 505 exact native IDs across modalities; 288 ever have `tokens` or `input_tokens` pricing | Numeric API pricing from 2024-06-18 |
| DeepInfra early pricing/model pages | All 13 pricing captures and 10 model-page captures returned before the first API capture | 35 IDs linked from token-price tables; two do not occur in the recovered API catalogs | Exact linked identities from 2023-12-01; numeric token-price rows from 2024-04-17 |

AWS totals are **1,791 service-scoped billing SKUs**, not unique models. Of those,
1,251 have an explicitly token-named native unit at least once; these include
embedding/training dimensions as well as inference. Other units include hours,
images and generic `Units`. A token-related usage label with `Units` does not by
itself establish a token denominator.

DeepInfra's 505 API IDs include non-token products. The two additional early-page
IDs are `01-ai/Yi-6B-200K` and `amazon/MistralLite`: their table prices are missing
in these captures, so they add historical identities, not numeric quotes. The
combined observed identity set is 507; it is not a count of unique underlying
models or continuously available products.

## What was recovered

The [compressed research report](research/aws-deepinfra-2026-10-26.json.gz) includes
the complete AWS SKU roster, DeepInfra API ID roster, snapshot/source receipts,
ordered presence references, pricing-difference candidates and early HTML table
extracts. Its [checksum manifest](research/aws-deepinfra-2026-10-26.manifest.json)
binds compressed/uncompressed hashes, exact byte sizes and headline counts. It is a research artifact,
not a generated public catalog or complete retained source archive.

Exact raw responses and full snapshot extractions are staged locally under
`/tmp/token3-history-probe/`, outside production data. They are temporary and not
committed. Before a real import, retain exact evidence durably with the separate
bounded storage/validation design described in the source map. The report alone
cannot reconstruct every original response byte or every unchanged price row.

### AWS: broad structured evidence, with clear billing boundaries

Across the 40 files there are **14,987 price-dimension assertions**, including
repeated unchanged dimensions. Every product was checked for `us-east-1`; every
file's service and version matched the requested immutable version URL. The
downloaded raw bytes have SHA-256/byte receipts. All returned products and term
types were inspected, independently of today's reviewed aliases.

There are **41 adjacent-version amount-difference candidates** for matching
service/SKU/term/offer/rate-code identities. For those candidates the compared
product attributes, term attributes, unit, range, applicable products and currency
keys are unchanged. Nevertheless, these remain candidates for historical review:
description changes, source effective dates and applicability still need checking.
Only 15 have the source feature `On-demand Inference`; the remainder include
training, model import and provisioned throughput. They must not all become token
inference price events.

Examples from exact same-SKU evidence:

| Native SKU / product | Published amount change | Source terms on the later side |
| --- | --- | --- |
| `WK92UTYU8723FP82`, Titan Text G1 Express input | USD 0.0013000000 → 0.0008000000 per 1K tokens | `effectiveDate: 2023-11-29T00:00:00Z` in version `20231221223942` |
| Same SKU | USD 0.0008000000 → 0.0002000000 per 1K tokens | `effectiveDate: 2024-05-01T00:00:00Z` in version `20240529225846` |
| `9XHSKPBV6R8E4FUY`, Titan Text G1 Lite input | USD 0.0003000000 → 0.0001500000 per 1K tokens | `effectiveDate: 2024-05-01T00:00:00Z` in version `20240529225846` |

The report retains both full price dimensions for each candidate, their source
snapshot references and the original amounts/units. These examples are from the
official [versioned Bedrock files](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/index.json).
We have not converted them into reviewed USD-per-million history.

**255 historical SKUs are absent from their service's latest retrieved file**:
seven in Bedrock and 248 in Foundation Models. That is source-listing evidence,
not 255 product retirements. All 248 SKUs in the earliest Foundation Models file
are absent from its subsequent retrieved version; later files use other SKU IDs
and include different native units. Continuity or renaming across those identities
needs explicit evidence, not name matching or guessed rate conversions.

### DeepInfra: useful numeric history plus genuine historical-only identities

All **31 API replay bodies matched their corresponding archive CDX SHA-1 digest**;
SHA-256/bytes are also retained. Some bodies are gzip-encoded: original bytes and
their archive digest were checked before decompression. Parsed catalogs are
nonempty arrays with distinct native model IDs; there were no duplicate IDs in
any of the 31 captures. The replayed catalogs contain **6,980 record assertions**,
not 6,980 unique models.

Compared with the committed DeepInfra native catalog identified by its hash in
the report, **113 recovered API IDs are absent**, including 12 that had token-based
pricing. Compared with the latest replayed capture, 109 IDs are absent. These
denominators differ because the committed catalog and archive capture are different
observations. Retained deprecated entries in a catalog do not prove availability.

Examples of token-priced IDs absent from the committed catalog include:

- `01-ai/Yi-34B-Chat`
- `HuggingFaceH4/zephyr-orpo-141b-A35b-v0.1`
- `codellama/CodeLlama-34b-Instruct-hf`
- `databricks/dbrx-instruct`
- `meta-llama/Llama-2-7b-chat-hf`
- `mistralai/Mixtral-8x22B-v0.1`

There are **1,247 pricing-object differences** between IDs present in adjacent
captures, including presentation, schedules, discounts and cache/tier fields.
Of these, **209 involve different base input/output cents-per-token fields** while
both sides say `type: tokens`. Neither count is a reviewed tariff-change count.
Conditions, quantization, context, service tiers, discount windows and source
currency need review before constructing economic events. All candidate before/
after pricing objects and selected scope fields remain in the report.

The largest gap between API captures is **126.683 days**, from 2025-07-30 to
2025-12-04; other gaps are about 81, 70, 66 and 60 days. A price can change and
revert during those gaps without appearing in our evidence. Capture differences
establish endpoint observations, not an exact intervening change date.

### Earlier pages extend numeric evidence to April 2024

All **23 early HTML replays also matched their CDX digests**. The earliest pricing
capture, 2023-02-20, is a small application shell without a price table. December
2023 through February 2024 pricing tables contain exact model-page links but `-`
in their price cells. Those missing amounts remain unknown, never zero.

The [2024-04-17 pricing replay](https://web.archive.org/web/20240417184927id_/https://deepinfra.com/pricing)
contains numeric token-price rows. A later
[2024-04-22 replay](https://web.archive.org/web/20240422133419id_/https://deepinfra.com/pricing)
shows different prices for the same linked model ID:

| Linked native identity | April 17 published input / output | April 22 published input / output |
| --- | --- | --- |
| `mistralai/Mixtral-8x7B-Instruct-v0.1` | `$0.27` / `$0.27` per 1M tokens | `$0.24` / `$0.24` per 1M tokens |

The comparison preserves each page's column headers, context cell, exact link,
row/table position and timestamp. It does not assign an exact price-change date.
The source prints `$`; the research keeps that symbol without silently filling
an ISO currency code. The API's native `cents` amounts similarly remain native
until historical currency evidence is reviewed. Current parser behavior does not
retroactively establish every old source's billing contract.

Across these early pages we extracted **142 numeric token-table row assertions**
and **73 rows with missing prices**. These include input-only embedding tables,
which have no invented output quote. GPU-hour tables are retained as separate
source evidence and excluded from those token-row counts. Localized code examples
and marketing snippets in page scripts are not treated as model-specific quotes.

## Limits and next implementation steps

This pass covered both advertised AWS version indexes in the existing region,
the exact DeepInfra API URL and the pre-API captures of two page URLs. It did not
enumerate every AWS region, every historical endpoint/URL variant, every later
DeepInfra HTML capture or every archived model-detail page. An additional API
prefix-index query returned HTTP 503; predecessor/query-variant completeness is
therefore unresolved. Empty or failed searches never establish absence.

The AWS version indexes are source-bounded completeness evidence. They do not prove
that every intra-version price revision is still retrievable. Their version begin/
end dates, publication dates and term effective dates are separate fields; in
particular, a version number timestamp is not a model launch date or a
contemporaneous observation of its earliest reported effective date. See the
[AWS index field definitions](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/service-version-index-file-for-aws-service.html).

Recommended next work:

1. Build the separate retrospective evidence ledger and durable byte retention,
   starting with the 40 AWS files, 31 API captures and 23 early page captures
   already validated locally. Preserve ordered snapshot references and original
   production observations. Do not feed old snapshots into current collectors.
2. Extract native assertions for all supported historical IDs, including unknown
   prices. Preserve AWS billing-dimension identities and DeepInfra exact linked
   IDs, native units, pricing objects, scopes and lifecycle fields. Keep the two
   HTML-only IDs even though their rates are unknown.
3. Review historical scope/currency and classify differences before public price
   charts. Use separate listing, billing-rule and amount assertions; matching
   names, disappeared SKUs or changed display strings are insufficient.
4. Extend earlier DeepInfra recovery through archived model-detail/catalog URL
   variants and official historical documentation. Retry the failed prefix query
   during that discovery pass; the currently demonstrated numeric lower bound is
   April 17, 2024, not proof that older evidence cannot be recovered.

No new paid service, credential, inference call, database, collector dispatch,
production write, deployment or workflow-gate change was involved. Existing
reviewed/native boundaries and the other 24 providers' collection remain intact.

## Verification

The evidence checks verify source SHA-256/bytes, all 54 DeepInfra replay digests,
AWS service/version/region, unique API IDs, roster/count reconstruction, retained
native amounts, research-only status and the compressed report manifest. These
are live public-source research checks plus local evidence reconstruction, not
production collector or GitHub CI results. Local reconstruction passed for all
94 source bodies, the 54 archive digests, all identity rosters and all 250 reported
difference candidates against their original source values. Public-catalog
visibility checks found no private-marked records. The compressed research report
passed its manifest/hash and JSON round-trip checks.

All 11 tests in `python3 -m unittest discover -s tests -p test_documentation.py -v`
passed, along with `git diff --check`. README and the parent research guide link
this follow-up. No established operating rule changed, so AGENTS needs no further
edit for this pass. The full application suite is unnecessary because application
behavior and production data are unchanged.
