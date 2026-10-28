# Historical target recovery — 2026-10-26–27

This continues the [1,000-capture checkpoint](historical-backfill-continuation.md)
after the user requested investigation of all 3,556 remaining targets and
exhaustion of feasible recovery methods. Research started on October 26 in
America/Los_Angeles and continued into October 27. Exact retrieval and archive
timestamps remain separate in the retained records. Index query cutoffs remain
their actual recorded request parameters, not an invented end-of-day census.

The completed append retains **7,560 captures, 706,650 assertions and 11,820
coverage rows** in 69 immutable segments. Coverage rows include both per-capture
interpretation and retained failed/deferred/empty lookup checks; they are not all
outstanding failures. Counts are evidence records, not unique models or price
changes. Every one of the 6,246 source/segment files from the preceding snapshot
and its ordered 65-segment prefix was verified unchanged.

## What was wrong with the backlog

The 3,556 were replay targets, not missing models or confirmed missing prices:
3,002 had never been attempted, 532 had transport failures, 15 failed digest
matching, three encountered denied redirects, and four were classified as
extractor failures. They were not 3,556 permanently inaccessible archives.

Reusable HTTPS sessions recovered most targets after short-lived connections
had failed. Identity encoding, preserved attempts, no-cache retries and later
exact replay attempts recovered further bodies. Successful requests still had
to match the selected timestamp/URL/CDX digest witness; an HTTP 200 alone never
became historical pricing evidence.

The receipt key also omitted the digest. Multiple CDX entries sometimes share a
URL and timestamp but identify different payloads. This reused a receipt for the
wrong target and produced misleading extraction failures. Receipts now include
the digest; legacy checkpoints remain readable but undergo digest verification
before extraction. Original failed/deferred checks remain retained when later
captures resolve their targets.

## Expanded source recovery

The work also checked predecessor URLs and actual current collector URLs, rather
than assuming the initial source list covered them:

- Nebius's former `/prices-ai-studio` page supplies archived model/flavor prices
  in ARIA tables. The reader preserves explicit cells, blank identifiers,
  source unit text and flavor distinctions without filling in absent model IDs.
- Azure's older pricing pages include regional `data-amount` JSON behind visible
  `$-` placeholders. Separate research reconstructs those expressions and their
  exact row/column headers; it does not interpret placeholders as zero or infer
  ISO currency. Locally malformed tables cannot establish model/column mappings.
- Oracle's general price list supplies past Generative AI SKU context; unrelated
  compute/storage rows are outside the selected scope. Its actual public pricing
  API additionally has archived native part numbers, metrics and currency-localized
  rates. Transactions are not converted into tokens or characters by inference.
- Nebius's public `models_info` archives retain model IDs, flavors, regions,
  quantization, limits and per-million-token fields. Missing currency remains
  unknown. Vendor throughput/quality figures do not enter public projections.
- Current markdown source URLs were checked alongside HTML sources. Together's
  free document was included; its deposit-gated API and comparisons remain paused.
  Fireworks' authenticated catalog URL was checked only in the public archive
  index, which returned no entries for that exact key; no authenticated request
  was made. Google Cloud Billing archive-index queries use no collector key.
- The 177 unsampled HTML index entries represented 176 distinct targets; all were recovered.
  Its original 31 API targets and all 40 AWS versions in the two retained version
  indexes were already present. AWS coverage remains the selected `us-east-1`
  scope, not every region. DeepInfra's embedded Next.js model/pricing records are
  also decoded in separate research, preserving source IDs and billing expressions.
- Snowflake research reads aligned Table 6(a) rows, including explicit Input/Output
  columns and table continuations across PDF pages. Credits and AI Credits remain
  distinct. Attached footnote markers remain in feature text; exact API IDs and
  full tariff applicability remain unreviewed. There is no credits-to-USD conversion.

One DeepInfra body uses Brotli rather than UTF-8/gzip. Its exact bytes remain in
the native ledger with an unparsed-encoding state. Separate research uses the
pinned, bounded Brotli decoder to reconstruct its embedded document data. No
original source or observation is replaced by decoded bytes.

### Independent archive: Arquivo.pt

All 97 selected exact source URLs across the 25 archive-backed provider profiles
were also queried in Arquivo.pt; AWS remains covered separately by native version
indexes. Twenty-seven queries returned indexes, containing 311 successful entries
and 307 distinct timestamp/URL/digest targets after deduplication. All 307 targets
were recovered and verified against the retained Arquivo.pt indexes. Seventy
queries returned empty HTTP-200 responses; these are explicit lookup checks, not
fabricated captures or evidence of absent tariffs. No query reached the 5,001-entry cap.

The ledger distinguishes `arquivo_index_v3` and `arquivo_native_v3`, the actual
`arquivo.pt` replay URLs and archive scope. Each body must match its own retained
index's exact URL, timestamp, HTTP-200 status and SHA-1 digest. Publication and
tariff-effective dates remain unknown. This follows Arquivo.pt's documented
[original-file replay interface](https://github.com/arquivo/pwa-technologies/wiki/APIs).
The two initially mismatched Oracle bodies recovered with gzip transport; another
OpenAI body recovered after a transient transport failure. All original bytes are
retained rather than replacing them with replay-rewritten pages.

Arquivo.pt adds captures for 20 groups, including Azure evidence from October
2022. These captures supplement the history under their own real dates and hashes;
they do not resolve a different missing Wayback timestamp/digest by substitution.

## Remaining public-access limits

The original backlog has 17 unresolved exact targets. Three more remain from
newly discovered URLs. These are exact payload gaps, not wholly missing providers:

| Provider | Remaining targets | Reason |
| --- | ---: | --- |
| Gemini API | 12 | Eleven alternate digests at two shared timestamps; one markdown replay redirects into an OAuth flow |
| Microsoft Foundry | 2 | Alternate digests at a shared pricing-page timestamp |
| Fireworks | 1 | Alternate digest at a shared timestamp |
| OpenAI API | 1 | Alternate digest at a shared timestamp |
| xAI | 2 | One HTTP 403; one redirect to a different capture date |
| Z.ai | 2 | Alternate digests at shared timestamps |

The other indexed groups have no outstanding targets in the completed selected
queues, and the additional Arquivo.pt queue has no unresolved targets. That does not establish complete provider-wide histories or continuous
tariff intervals. Earlier archive bodies at the redirect destination are retained
under their real dates; they do not substitute for the requested date.

Identity, image/iframe/object replay modes, content-encoding/no-cache changes,
browser/markdown request headers, exact digest checks and public CDX storage
metadata were investigated for the remaining cases. Rewritten bodies did not
establish the missing digests. Public CDX responses did not expose WARC filenames
or offsets for selecting the inaccessible variants. Another body at each shared
timestamp was recovered; the unknown variants are not assumed economically identical.

### Common Crawl file fallback

Common Crawl's collection list was available, but its query API repeatedly
returned HTTP 504, including minimal older-collection queries and another web
transport. Direct public archive files provided a working fallback. The
[dated scan report](research/historical-commoncrawl-recovery-2026-10-27.json)
records all 73 selected published collections from 2019 through October 2026,
the 98 selected URLs, exact master-index hashes and actual retrieval timestamps.
All selected collection scopes completed after retrying unavailable blocks;
this does not establish provider-wide histories or continuous tariff intervals.

The scan uses Internet Archive's SURT canonicalizer, checks the predecessor and
intersecting sparse-index blocks, and retains each original HTTP/slash variant
that matches a selected provider source. A newly found predecessor,
`https://readme.fireworks.ai/page/pricing`, was checked across all collections;
Wayback independently supplied November 2023 and February 2024 captures.
Its empty Arquivo.pt response remains an explicit lookup check.

The 533 Common Crawl payload targets were all retrieved. Public Hugging Face
mirrors recovered 186 of the first 217 when the original host denied access;
the original host recovered after a cooldown and supplied every target. Requests
used two paced workers, bounded ranges/retries, checkpoints and 4 GiB phase budgets.
No paid query, private access, login, provider inference request or archive-save
submission was used. The implementation follows Common Crawl's documented
[public file/range interfaces and mirrors](https://www.commoncrawl.org/get-started).

`commoncrawl_index_v4` retains exact bounded gzip CDX blocks, scoped to the
selected source URL. `commoncrawl_native_v4` retains exact gzip WARC records,
with original storage/retrieval URLs and byte ranges. Offline validation checks
the CDX URL/date/digest/storage witness, WARC target/date/type/length, available
block digest, HTTP status and exact payload SHA-1 before parsing. Raw WARC and
neighboring index bytes are never copied into the public app. Two responses are
explicitly archive-truncated: their exact bytes and interpretation state remain,
but no pricing assertions are extracted from incomplete documents.

The [method receipt report](research/historical-recovery-methods-2026-10-26.json)
retains compact metadata and receipt hashes for 110 diagnostic requests across
replay modes, storage metadata and Common Crawl. Diagnostic response hashes are
not historical prices. Eighteen locally decoded saved response variants were
also checked against the remaining digests; none matched. A separate
bounded [checksum reconstruction probe](research/historical-payload-reconstruction-2026-10-27.json)
tested 17,690 common gzip/header and Brotli candidates from 58 saved bodies;
none matched the unresolved indexed payloads. No generated candidate became a
capture or pricing assertion. The
[licensed community-history report](historical-corroboration.md#licensed-community-history-datasets)
retains additional attributed, commit-pinned data without substituting publisher
dates for missing archive witnesses.

These records describe the tested public recovery routes and their present
limits. They do not claim that every possible Internet source has been exhausted
or that archive availability cannot change later.

## Per-provider result

Every indexed group has some recovered numeric price evidence or a conservative
price candidate. **None has a proven complete history.** Structured native means
amounts were present in source fields; it does not establish economic equivalence,
reviewed quotes or complete billing applicability. Document/PDF candidates require
further model/rate review. The linked machine-readable audit provides dated counts.

| Provider group | Strongest recovered evidence | Outstanding exact targets | Main remaining limitation |
| --- | --- | ---: | --- |
| Alibaba Model Studio | Document price candidates | 0 | Original currencies, tiers and prompt bands still need review; Qwen is a family |
| Anthropic | Document price candidates | 0 | Historical tier/cache conditions and tariff intervals remain partial |
| Microsoft Foundry | Document and embedded regional price candidates | 2 | Alternate payloads unavailable; regional expressions and API identities need review |
| Amazon Bedrock | Structured native SKU dimensions | 0 | All 40 selected native versions retained; selected `us-east-1` scope only |
| Cloudflare Workers AI | Document price candidates | 0 | Neuron/token billing applicability remains source-specific |
| Databricks | Document price candidates | 0 | DBU amounts are not USD/token prices |
| DeepInfra | Structured native API fields and embedded pricing | 0 | Complete selected queues; older gaps and tariff continuity remain unproven |
| DeepSeek | Document price candidates | 0 | Historical cache/promotion conditions and effective intervals remain partial |
| Fireworks | Document price candidates | 1 | Exact replay unavailable; identical payload retained one second later; older model/rate alignment remains unreviewed |
| Gemini Developer API | Document price candidates | 12 | Eleven alternate payloads and one OAuth redirect; kept separate from Vertex |
| Groq | Document price candidates | 0 | Partial archived dates; historical identities/applicability need review |
| Hugging Face Inference | Structured native provider-route fields | 0 | Route billing is not inferred upstream-provider equivalence |
| MiniMax | Document price candidates | 0 | Different modalities and original units require separate review |
| Nebius Token Factory | Structured native model/flavor fields | 0 | Currency unknown where absent; flavors remain distinct |
| Novita | Structured native model fields | 0 | Full historical billing scope and tariff intervals remain unreviewed |
| OpenAI API | Document price candidates | 1 | One alternate payload unavailable; unqualified historical cache writes remain retention-unverified |
| OpenRouter | Structured native model pricing | 0 | Aggregator billing and source-native IDs remain separate from reviewed identities |
| Oracle Generative AI | Structured native SKU/localized price fields | 0 | Character/transaction/token scopes are not converted by inference |
| OVHcloud AI Endpoints | Structured native pricing fields | 0 | Currency remains unverified |
| Scaleway Generative APIs | Document price candidates | 0 | Partial dates and original regional/currency scope |
| Snowflake Cortex | PDF layout price candidates | 0 | Model-to-feature/rate mapping and footnotes remain unreviewed; Credits and AI Credits are distinct |
| Together AI | Document price candidates | 0 | Comparisons remain operator-paused; no deposit-gated API access |
| Vercel AI Gateway | Structured native gateway pricing | 0 | Gateway billing, not inferred upstream-provider quotes |
| Vertex AI | Document price candidates | 0 | Separate billing source; no invented historical Cloud Billing tariff from rolling timestamps |
| xAI | Document price candidates and attributed reports | 2 | One HTTP 403, one date-changing redirect, plus retained conflicting older reports |
| Z.ai | Document price candidates | 2 | Two alternate payloads unavailable; historical price conditions remain partial |

The Fireworks target at `2025-10-01T20:07:13Z` has the same verified SHA-1
(`OCRBHAUHDVMAW7AA6FWW7YIU6HTP23ER`) as a retained capture one second later.
Its source bytes are therefore available, but that does not establish a successful
replay at the missing timestamp. The audit records this payload match separately;
the other 19 unresolved direct targets have no matching retained payload digest.

## Reproduce and inspect

Import remains explicit and atomic, through bounded staged manifests. The
warehouse retains every earlier source/segment byte and its ordered segment
prefix. New evidence stays comparison-ineligible; current observations, aliases,
reviewed prices and provider policies are unchanged.

The [price-coverage audit](research/historical-recovery-price-coverage-2026-10-26.json)
lists all 26 providers and their evidence grades. The
[target audit](research/historical-recovery-targets-2026-10-26.json) binds the same
verified snapshot and distinguishes retained targets from remaining failures.
Counts describe captures, assertions or candidates, never unique models or price
changes. The separate [corroboration and decoding guide](historical-corroboration.md)
explains report provenance and uncertainty.

```bash
python -m scripts.prepare_deepinfra_history --stage-dir /path/to/deepinfra-stage
python -m scripts.prepare_arquivo_history --stage-dir /path/to/arquivo-stage
python -m scripts.prepare_commoncrawl_history --stage-dir /path/to/commoncrawl-stage
python -m scripts.historical_research_pipeline \
  --output-dir docs/research --research-day 2026-10-26 \
  --stage-dir /path/to/original-stage --stage-dir /path/to/alternate-stage \
  --stage-dir /path/to/current-source-stage --stage-dir /path/to/deepinfra-stage \
  --stage-dir /path/to/arquivo-stage \
  --stage-dir /path/to/commoncrawl-stage --stage-dir /path/to/fireworks-predecessor-stage \
  --baseline-checks /path/to/original-3556-checks.json
```

Research reports remain outside the public app allowlist. Large derivative reports
use checked, content-addressed gzip segments capped at 16 MiB uncompressed and a
bounded manifest. The public historical projection still publishes selected native
fields in validated JSON chunks, with 512 KiB limits on wire and decoded content
and lossless gzip envelopes when smaller. Its temporary record-by-record build
bridge is private, count-checked and deleted after use. The recovery task itself
did not deploy a website release. The user's subsequent October 27 request to add
the recovered history to the website authorizes publishing this native snapshot
through the existing Historical evidence view. Separate derivative research
reports remain outside the app allowlist and current comparisons.

## Local verification — October 27, 2026

`npm run check` passed all 113 frontend tests, 346 Python tests, TypeScript and
the production build. All 55 Chromium end-to-end tests passed against that static
build, including complete filtered historical exports, corrupt-chunk recovery,
mobile layout and automated WCAG 2.1 AA checks. Workflow lint and documentation
checks passed. The generated site contains 3,318 files totaling 258,392,633 bytes,
below the enforced 1,000,000,000-byte build limit. Source archives and research
artifacts remain outside the public asset paths. These are local results; this
task has not deployed a new website release.
