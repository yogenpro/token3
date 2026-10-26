# Historical ledger expansion — 2026-10-26

The authorized expansion adds selected public evidence for all 24 remaining
indexed provider groups. Together with the original AWS Bedrock/DeepInfra batch,
the warehouse covers all 26 groups. This is partial source recovery, not complete
price history. Assertions remain `comparison_eligible: false` and
`unreviewed_historical`; no reviewed quote, alias, current collection observation
or public projection is changed.

The [machine-readable coverage report](research/historical-expansion-2026-10-26.json)
records the exact preparation time, interpretation states and gaps by provider.
The [versioned source profiles](../config/historical_sources.json) select 43 URLs.
Their retained archive indexes yield 4,410 replay candidates after deduplicating
identical provider/timestamp/original-URL/digest entries across indexes. Those
entries are archive references, not 4,410 models or price changes.

This batch retains **339 captures and 30,819 assertions**: 43 archive indexes,
292 validated archived bodies and four current retirement/deprecation documents.
It also retains **4,118 standalone coverage checks**: 3,562 deferred replays,
552 failed transports with no HTTP response, and four extractor-rejected bodies.
296 replay bodies were retrieved; four were rejected before import. Connection
failures occurred in the local execution transport and do not establish vendor
outages. Rejected bodies stay outside the ledger; no failed lookup becomes an
empty catalog or evidence of retirement.

After this append the ledger contains **438 captures, 53,013 assertions, 4,557
coverage records and zero corrections**, including the original batch unchanged.
Evidence counts include document rows, narrative blocks, PDF pages and native
catalog records; they are not unique-model, comparable-price or price-change
counts. Large source tables can dominate assertion counts.

## Evidence by provider

`Indexed` counts returned index rows before cross-index deduplication. `Retrieved`
counts replay bodies, including the four rejected bodies. `Captures` counts
accepted indexes, archived bodies and selected current documents. The date span
is the earliest/latest **retained archive capture**, not launch dates, tariff
validity intervals, continuous coverage or retirement dates. Current retrospective
documents do not extend the archive span.

| Provider | Indexed | Retrieved | Captures | Assertions | Retained archive span |
| --- | ---: | ---: | ---: | ---: | --- |
| Alibaba Model Studio | 38 | 16 | 18 | 20,440 | 2026-01-16 to 2026-10-19 |
| Anthropic | 652 | 14 | 18 | 812 | 2025-05-12 to 2026-10-24 |
| Azure | 19 | 11 | 15 | 753 | 2023-08-08 to 2026-09-29 |
| Cloudflare | 101 | 14 | 15 | 304 | 2024-03-01 to 2026-10-26 |
| Databricks | 35 | 15 | 17 | 408 | 2024-04-15 to 2026-08-29 |
| DeepSeek | 292 | 13 | 14 | 86 | 2024-11-07 to 2026-10-26 |
| Fireworks | 184 | 13 | 15 | 338 | 2024-01-24 to 2026-10-17 |
| Gemini Developer API | 905 | 11 | 9 | 535 | 2023-12-13 to 2026-10-24 |
| Groq | 233 | 14 | 15 | 205 | 2024-03-01 to 2026-10-25 |
| Hugging Face | 61 | 11 | 13 | 162 | 2025-04-01 to 2026-10-12 |
| MiniMax | 119 | 12 | 14 | 159 | 2025-12-03 to 2026-10-21 |
| Nebius | 7 | 7 | 8 | 210 | 2025-04-04 to 2025-10-17 |
| Novita | 55 | 12 | 14 | 119 | 2025-01-22 to 2026-09-16 |
| OpenAI | 455 | 13 | 17 | 654 | 2023-02-09 to 2026-10-26 |
| OpenRouter | 232 | 12 | 13 | 1,855 | 2023-07-26 to 2026-10-25 |
| Oracle | 3 | 3 | 6 | 202 | 2026-04-23 to 2026-09-23 |
| OVHcloud | 65 | 13 | 15 | 408 | 2025-11-07 to 2026-10-17 |
| Scaleway | 31 | 11 | 12 | 427 | 2025-01-30 to 2026-10-22 |
| Snowflake | 81 | 14 | 15 | 148 | 2021-04-24 to 2026-10-12 |
| Together | 524 | 12 | 15 | 330 | 2023-07-14 to 2026-10-25 |
| Vercel | 113 | 13 | 15 | 1,289 | 2025-06-28 to 2026-10-24 |
| Vertex AI | 189 | 14 | 15 | 449 | 2024-03-10 to 2026-04-22 |
| xAI | 187 | 14 | 16 | 28 | 2025-01-21 to 2026-10-22 |
| Z.AI | 90 | 14 | 15 | 498 | 2025-07-28 to 2026-10-25 |

## Interpretation boundaries

`historical-native-v1` continues reconstructing the original AWS/DeepInfra rows
unchanged. `historical-native-v2` adds these conservative representations:

- Public catalog objects preserve exact native IDs, complete source objects and
  decimal lexemes without currency/unit conversion. Duplicate/private objects
  fail; pagination uncertainty produces explicit incomplete coverage, not a
  complete partial catalog. Hugging Face provider routes remain separate.
- HTML/Markdown evidence preserves heading paths, headers, cells, code IDs,
  links and narrative conditions. Only explicit identifier columns or a single
  code identifier in a model column establish native IDs; other evidence uses
  document-local IDs. Narrative blocks are bounded and retain location ranges.
  Ambiguous nested/incomplete tables retain visible text and an explicit
  interpretation state, without asserting aligned rate rows.
- Snowflake PDF pages retain unaligned text with the pinned existing PDF parser.
  A 2021 table-of-credits capture does not establish that a later AI SKU existed
  in 2021. No model-to-credit or credit-to-currency mapping is inferred.
- Current public retirement documents for OpenAI, Anthropic, Azure and Oracle
  preserve their actual retrieval dates and retrospective text. Publication,
  archive and reported-effective timestamps remain unknown unless independently
  supported; dates in prose are not automatically promoted to structured tariffs.

Gemini Developer API and Vertex remain separate sources. Qwen stays under Alibaba
Model Studio. Gateway rates do not become upstream-provider prices. OVHcloud
currency and Snowflake model/rate alignment remain unverified. Together recovery
uses free documents only; its deposit-gated API and reviewed comparisons stay
paused. No credentials, authenticated responses or inference endpoints are used.

An index-only source, unsupported encoding or ambiguous table remains visible as
such. The coverage report exposes these states. Even a complete returned snapshot
does not prove account-independent availability, price continuity or a model's
retirement. Historical-only IDs are retained independently of today's aliases;
recognizing an ID does not review its prices.

## Explicit staging and offline import

Use a disposable staging directory outside production data. Discovery is manual,
resumable and budgeted; it does not run in daily collection or write the ledger.
It defaults to two workers, 30-second request timeouts, 16 MiB bodies, at most
5,000 requests and 1 GiB per invocation. Redirects are constrained to the selected
public profiles or matching archive replay. Requests use no collector credentials.
The initial pass prioritizes the oldest/newest indexed entries across providers;
that is sampling order, not proof that all intervening history was recovered.

```bash
# Network staging; repeat --provider or omit it for the 24 expansion profiles.
python -m scripts.discover_historical_evidence \
  --stage-dir /tmp/token3-history --provider groq --max-requests 50

# Offline preflight: derive import files, interpretation states and coverage gaps.
python -m scripts.prepare_historical_discovery --stage-dir /tmp/token3-history

# Validate in an isolated temporary ledger, then explicitly append.
python -m scripts.import_historical_evidence \
  --input /tmp/token3-history/validated-sources.json \
  --checks /tmp/token3-history/validated-checks.json --dry-run
python -m scripts.import_historical_evidence \
  --input /tmp/token3-history/validated-sources.json \
  --checks /tmp/token3-history/validated-checks.json --apply
python -m scripts.historical_ledger verify
```

Failed/deferred checks have a null capture ID. Replay checks bind the exact
timestamp/URL/digest entry in a retained index. `checked_at` on a deferred lookup
records planning time, not a request or archive retrieval. Importing the same
prepared batch is idempotent; preparing later can append a new coverage check
without erasing the earlier one. Later successful recovery appends evidence and
does not silently delete the earlier failure. Selected index responses are
source-bounded and capped; a cap-reaching response never proves full history.

The preparer writes `validated-sources.json`, `validated-checks.json` and
`coverage-report.json`. Discovery's intermediate `sources.json`/`checks.json` are
staging diagnostics; use the validated files for import. Optional attached replay
and external-receipt modes support constrained transports while retaining the
same source hash/digest checks. HTTP status alone never establishes a capture.

Ordinary collection retains its temporary raw-response policy. Public history
UI was subsequently explicitly authorized and implemented through a separate
[public projection](dashboard-data-organization.md#historical-public-projection).
Comparable retrospective rates and additional source URLs still require their own review. See [ledger integrity and recovery](historical-evidence-ledger.md).

## Local verification

On 2026-10-26, `npm run check` passed 98 frontend tests, 292 Python tests,
TypeScript and the production build. The 36 historical tests also passed after
adding the mixed-version coverage retry assertion. Documentation/link checks
passed, as did `git diff --check`. Complete source reconstruction verified all
438 captures and 53,013 assertions. Re-importing the prepared real batch changed
no ledger file bytes, and the original four manifest segments remain the exact
prefix of the expanded eight-segment manifest.

Existing tracked live-data/catalog/policy files are unchanged. The built public
assets contain no historical warehouse paths, raw-body assets or byte copies of
retained compressed source assets. These are local checks; no hosted CI, live
production collection or release is claimed.
