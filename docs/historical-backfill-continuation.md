# Historical backfill continuation — 2026-10-26

This document preserves the 1,000-capture checkpoint and its local checks.
The subsequent [selected-target recovery](historical-target-recovery.md) supersedes
its outstanding-work counts and build resource bounds.

Research day is America/Los_Angeles; the completed staging preparation occurred
on 2026-10-27 UTC. This pass continues the same 4,410 selected replay targets,
without redefining them as all provider history. The user also explicitly accepted
[best-effort historical corroboration](historical-corroboration.md).

## Retained progress

A bounded continuation pass used reusable HTTPS connections after repeated local
connection refusals with short-lived curl processes. Source bodies still had to
match their exact retained CDX timestamp/URL/digest witnesses before import.
The temporary transport used an existing system HTTP client; no project dependency,
paid service, authenticated source or scheduled collector was added.

The append added **562 captures and 36,791 assertions**. The local ledger now has
**1,000 captures, 89,804 assertions, 5,157 coverage records and zero corrections**.
All eight pre-existing segments remain an exact ordered prefix of the new
12-segment manifest. Original observations, current provider catalogs, reviewed
quotes, aliases and provider policies were not changed.

The latest selected expansion corpus has **854 imported archived bodies out of
4,410 replay targets**, up from 292. It also retains 43 archive indexes and four
current retrospective documents; the original AWS/DeepInfra batch remains intact.
There are **3,556 remaining targets**:

- 3,002 deferred/unattempted targets;
- 532 failed transports with no provider HTTP response;
- 15 bodies failing exact archive digest matching;
- three denied redirects;
- four extractor-rejected targets.

Failed integrity checks remain excluded even under best-effort research. Unchanged
unattempted work did not produce thousands of new planning checks. Existing
failed/deferred checks remain retained when a later import succeeds; they are not
counted as still-outstanding targets after successful recovery.

[The staging coverage snapshot](research/historical-continuation-2026-10-26.json)
records per-provider counts and archive spans. Captures and assertions are not
unique models, confirmed prices, price changes or completeness percentages.

## Pricing evidence audit

[The generated pricing audit](research/historical-price-coverage-2026-10-26.json)
binds the retained ledger manifest and classifies each provider separately:
structured native price fields, numeric candidates in aligned document price
columns, attributed reported prices, or no numeric price history identified.
It retains example assertion IDs and source/date references for review.

This separates successful document recovery from actual pricing evidence.
Document candidates are heuristic leads. PDF page text, context/model-ID digits,
retirement dates, dynamic-price sentinels and missing cells do not automatically
become model prices. Counts can include non-token units and repeated captures.

The audit also found historical OVHcloud amounts nested under
`metadata.usage_information.pricing`. Both the audit and public field projection
now retain those selected native amounts/units without inferring currency,
copying inference endpoints or publishing performance measurements.

The completed audit identifies structured native amounts for seven providers,
numeric document candidates for fifteen, report-only pricing for three, and
unaligned PDF evidence without an identified model/rate mapping for Snowflake.
Hugging Face gained structured historical amounts in this pass; xAI gained
numeric document candidates as well as attributed reports.

The separate curated report catalog adds eight best-effort claims from seven
sources for xAI, Nebius, Azure and Oracle. Conflicting denominators stay explicit;
an inaccessible social link remains a lead. Oracle's reported character billing
is not converted to token billing. These report claims remain outside current
comparisons and the dashboard's public allowlist.

No new website release is part of this continuation. Local projected assets can
include the appended native evidence after validation; the new report catalog
requires a separately reviewed public projection before display.

## Per-provider pricing gaps

Statuses describe identified evidence, not completed provider-wide price histories.
Numeric document candidates still need interpretation; native amounts preserve
their original units/currency uncertainty. Outstanding counts apply only to the
selected indexed replay targets. The report catalog is separate from native captures.

| Provider | Best available backfilled pricing evidence | Outstanding replay targets |
| --- | --- | ---: |
| Alibaba Cloud Model Studio | Numeric document candidates | 21 |
| Anthropic API | Numeric document candidates | 600 |
| Microsoft Foundry | Attributed reports only | 7 |
| Amazon Bedrock | Structured native amounts | 0 |
| Cloudflare Workers AI | Numeric document candidates | 54 |
| Databricks | Numeric document candidates | 20 |
| DeepInfra | Structured native amounts | 0 |
| DeepSeek | Numeric document candidates | 248 |
| Fireworks | Numeric document candidates | 135 |
| Google Gemini API | Numeric document candidates | 854 |
| Groq | Numeric document candidates | 185 |
| Hugging Face Inference | Structured native amounts | 29 |
| MiniMax | Numeric document candidates | 73 |
| Nebius Token Factory | Attributed reports only | 0 |
| Novita | Structured native amounts | 29 |
| OpenAI API | Numeric document candidates | 402 |
| OpenRouter | Structured native amounts | 186 |
| Oracle Cloud Generative AI | Attributed reports only; character billing, not tokens | 0 |
| OVHcloud AI Endpoints | Structured native amounts; currency unverified | 28 |
| Scaleway Generative APIs | Numeric document candidates | 19 |
| Snowflake Cortex | PDF text; model/rate alignment unresolved | 33 |
| Together AI | Numeric document candidates | 243 |
| Vercel AI Gateway | Structured native amounts | 65 |
| Google Vertex AI | Numeric document candidates | 141 |
| xAI | Numeric document candidates | 139 |
| Z.ai | Numeric document candidates | 45 |

## Local verification

The final `npm run check` passed **106 frontend tests, 314 Python tests,
TypeScript and the production build**. All five historical browser tests passed
against the actual static build, including whole-filter exports, deep links,
corrupt-chunk recovery, mobile layout and WCAG checks in both themes. Documentation
checks and `git diff --check` passed. These are local results; no hosted CI or new
deployment is claimed.

The append verified persisted source bytes and complete re-extraction before
advancing the atomic manifest. The full-corpus projection test checked every
index/evidence binding, count and bounded content-addressed chunk. All original
source/segment file hashes were preserved, and the built app contains no copied
raw warehouse assets or report catalog.

The larger corpus exceeded the old 120-second projection setup budget. Vitest no
longer performs an unnecessary browser-asset preparation before its dedicated
real-corpus test. Setup/browser-server readiness now allows 240 seconds while
the actual verifier retains its existing 180-second bound; all source, schema,
hash, byte-limit and completeness assertions remain active. Chunk-to-index mapping
also avoids a redundant parse before the final persisted-chunk schema check.
