# Historical evidence ledger

The historical ledger is a separate **warehouse dataset**, implemented in Python
with versioned files and offline import/verification, without a backend, database or paid service.
It records recovered evidence without modifying live collection observations,
reviewed aliases, current prices or native event history. The authorized dashboard
view uses a separate read-only public projection; original ledger files stay outside
the app.

The first authorized import retained the public AWS/DeepInfra evidence examined in
the [dated research](aws-deepinfra-history-research.md). The subsequent authorized
[expansion](historical-ledger-expansion.md) adds selected public evidence for the
other 24 groups. Versioned exact URL profiles and native catalog, document and PDF
extractors now cover all 26 indexed groups. Historical-only identifiers do not need
reviewed aliases. Coverage remains partial. Adding another source requires its own
public-source boundary and reconstruction tests, not an alias or price conversion.

The [subsequent recovery](historical-target-recovery.md) also supports independently
witnessed Arquivo.pt indexes/replays and exact public Common Crawl CDX/WARC byte
ranges. Their archive namespaces, source URLs and dates remain distinct. WARC
containers and payload digests are verified before extraction; archive-truncated
responses retain their bytes/state with zero pricing assertions. Public projections
can include validated storage/retrieval URLs and byte ranges, but never the raw
index, HTTP headers, WARC, source-response bytes or warehouse assets. Human image
transcriptions and licensed community datasets remain separate attributed research.

## What is retained

The **initial 2026-10-26 import** had 99 captures, 22,194 assertions and 100 coverage
records (99 capture-derived plus one separately reported failed lookup), with zero
corrections. These are evidence counts, not unique-model,
reviewed-offering, price-change or current-availability counts:

- Two AWS service-version indexes and three exact-URL archive indexes.
- All 40 advertised AWS version files in `us-east-1`, including both Bedrock feeds.
- All 31 returned DeepInfra public API captures, plus 23 early pricing/model pages.
- 14,987 AWS billing-dimension assertions, 6,980 DeepInfra model assertions and 227
  HTML table-row assertions. The latter include GPU-hour evidence as well as
  token tables; no GPU-hour rate is relabeled as a token price.

The source roster and gaps are in the research reports. The ledger preserves
original downloaded response bytes durably rather than depending on temporary
research files or continuing archive availability. Only the already downloaded
public evidence was imported in that initial batch; no fresh provider or archive
request was necessary for it. Subsequent expansion uses separate explicit public
discovery staging; see [its retained counts and gaps](historical-ledger-expansion.md).

## Storage and integrity

```text
data/historical_evidence/manifest.json
data/historical_evidence/sources/<sha256>.bin.gz
data/historical_evidence/segments/<sha256>.jsonl.gz
```

Schema 1 uses policy `historical-evidence-v1`. Source and segment filenames address
the **stored gzip bytes**. Each reference also binds the exact uncompressed
SHA-256 and byte size; segment references add record counts. Every source body
and JSONL segment is bounded to **16 MiB uncompressed**. JSONL segments end at
record boundaries. An oversized source or single assertion fails explicitly.
Encoded size and manifest size are bounded too; the manifest cap is 4 MiB.

The initial retained snapshot contains 99 source assets and four assertion/metadata
segments, about 7 MiB compressed in total. The ordered manifest is the sole commit
point. Files not referenced by it are not part of the ledger.

Source bodies are byte-exact, including original gzip encoding where present.
Restoring a gzip-encoded API response returns those original encoded bytes, not a
reformatted JSON document. Source decompression and stored-asset decompression
have independent bounds. Archived replays are checked against an exact retained
CDX entry and its SHA-1 content digest before parsing; SHA-256 also binds the
retained bytes. AWS service/version/region/publication and index version-scope
witnesses are checked against the retained official files. This verifies retained
evidence consistency; it is not a provider digital-signature system.

## Record types and dates

Every record has a deterministic, full SHA-256 identity computed from its kind and
canonical payload. Records accumulate in manifest order; an identical import is
a no-op. Record order is import order, not an invented global tariff chronology.

| Kind | Meaning |
| --- | --- |
| `capture` | Provider/source kind, exact original URL, optional exact replay URL and archive digest, original retrieval timestamp, archive timestamp, explicit source publication timestamp, source request scope and retained raw-body reference. |
| `assertion` | Source-native identity, source scope, extractor version, exact JSON pointer or table/row location, native record/billing evidence, explicit source-reported effective timestamp where present, and `comparison_eligible: false`. |
| `coverage` | Reproducible counts and interpretation of a capture: index only, complete returned snapshot, visible tables only, or no structured tables. Separately reported failed lookups have a null capture ID and explicit operator provenance. Neither form claims continuous historical coverage or account-independent availability. |
| `correction` | An explicit operator reason/time connecting a later retained assertion to an earlier assertion it supersedes. Both assertions and their sources remain readable. |

There is no fabricated `observed_at`. `retrieved_at`, `archive_capture_at`,
`source_published_at` and `source_reported_effective_at` have different meanings.
They are never substituted for each other. Request/version intervals remain in
their own source scope. A price-effective date may be unknown, or an explicitly
announced future date; neither becomes a claim that the price was currently billed.

AWS assertion identities preserve full rate codes, SKU, service, term type,
offer, region, original product fields, term fields and price dimensions. Products
without terms can remain unpriced assertions. Units, decimal strings, currencies,
ranges and conditions are not converted.

DeepInfra API assertions retain the entire source-native model object, including
pricing objects, schedules, discounts, cache/tier rules, quantization and native
lifecycle fields. JSON decimal-number lexemes are represented as strings during
extraction to avoid floating-point rounding; exact original JSON types and bytes
remain in the source asset. Integer fields remain integers. Native `cents` fields
are not automatically converted to USD, and lifecycle numbers are not assigned
unverified timestamp semantics.

HTML assertions preserve headers, cells, exact links and alignment state. An exact
model-page link can establish a native identity; an unlinked row uses a
document-local identity. A dash remains a dash, not a zero. `$` does not silently
become an ISO currency code. Scripts/narrative are retained in the source body
but are not extracted as pricing assertions. Nested/incomplete tables fail closed.

All assertions remain `unreviewed_historical`. Retired/absent listings are not
inferred from missing captures. Repeated content can share one source asset, but
separate capture records preserve A → B → A evidence and capture order. No
native-to-reviewed promotion, canonical alias creation or automatic economic-event
classification occurs here.

## Commands

Use the project's Python environment (Python 3.9+, 3.12 recommended). Writes use
Unix `flock` and refuse concurrent writers; no new Python dependency is needed.
These commands make **no network requests**.

```bash
# Read-only full verification, including reconstruction of every assertion.
python -m scripts.historical_ledger verify

# Inspect a complete historical identity, with source and correction references.
python -m scripts.historical_ledger inspect \
  --provider deepinfra --native-id meta-llama/Llama-2-7b-chat-hf

# Inspect all retained dimensions of an exact AWS billing SKU.
python -m scripts.historical_ledger inspect \
  --provider bedrock --sku WK92UTYU8723FP82

# Offline preview from a portable source-descriptor manifest; default is dry-run.
python -m scripts.import_historical_evidence --input /path/to/sources.json --dry-run

# Explicitly append that validated batch to the ledger.
python -m scripts.import_historical_evidence --input /path/to/sources.json --apply

# Combine staged manifests in order into one atomic append, retaining index labels.
# Each manifest remains capped at 4 MiB; at most 16 inputs are accepted.
python -m scripts.import_historical_evidence \
  --input /path/to/first/sources.json --input /path/to/second/sources.json --apply
```

Both modules accept `--ledger-dir /path/to/isolated-ledger`. Preview creates and
fully validates an isolated temporary ledger; it does not write the destination
or change its existing state. An applied import additionally verifies the existing
ledger before appending. No importer runs in the daily collection workflow.

`record-discovery-failure` accepts a supported public archive `--source-url`, actual
`--checked-date` and optional failure `--http-status`. It appends an operator report
with the current recording time, not a source capture. The retained HTTP-503 prefix
lookup has day precision because no exact lookup instant was retained during
research. It has no invented response body, archive timestamp or successful/empty
catalog. Repeating the same date/URL/status report is a no-op. There is no automatic
network retry or failure reporting workflow attached to this command.

For the initial local research receipts, the one-time adapter is:

```bash
python -m scripts.import_historical_evidence \
  --research-probe /tmp/token3-history-probe/probe.json --dry-run
python -m scripts.import_historical_evidence \
  --research-probe /tmp/token3-history-probe/probe.json --apply
```

This staging path is specific to the dated research session, not required for
normal reading or verification. Once imported, all required evidence and index
witnesses are within `data/historical_evidence/`.

The `restore` command requires a capture ID from inspection and a **new** output
path outside the ledger:

```bash
python -m scripts.historical_ledger restore \
  --capture-id CAPTURE_ID_FROM_INSPECTION --output /tmp/original-historical-source.bin
```

It verifies the ledger before restoring exact bytes and refuses to overwrite an
existing output. The placeholder capture ID above must be replaced with the real
ID; it is not example evidence.

### Portable input contract

The input JSON has exactly `schema_version: 1` and an ordered `sources` array.
Each source contains `label`, `body_path`, `body_sha256` and `metadata`.
`body_path` is a regular file relative to the input JSON directory; parent
traversal, symlinks, missing bytes and hash mismatches are rejected.

Metadata contains exactly `provider`, `source_kind`, `source_url`, `replay_url`,
`retrieved_at`, `archive_capture_at`, `archive_digest`, `source_published_at` and
`request_scope`. Unknown dates/replay fields are explicit nulls, not guessed
values. Currently supported request scopes are:

| Source kind | Required scope |
| --- | --- |
| `aws_version_index` | `service` (`AmazonBedrock` or `AmazonBedrockFoundationModels`) |
| `aws_price_list` | `service`, `region: us-east-1`, exact `version`, exact index `version_scope`, and `index_label` pointing to an earlier source in the batch |
| `archive_index` | `target_url`; the source URL must be a supported bounded exact-URL CDX query |
| `deepinfra_api`, `deepinfra_html` | `index_label` pointing to the retained archive-index source |

An existing retained index can instead be referenced by its `index_capture_id`.
Labels are batch-local conveniences and are replaced by stable capture IDs.
Include index descriptors before their dependent bodies. Successful source
receipts, hashes, and genuine retrieval timestamps must come from actual source
retrieval, not from today's file modification time or an invented backfill date.

Source URLs are restricted to the selected public AWS price-list paths,
DeepInfra's public model list/pricing/model pages, and supported archive queries.
Credentials, unknown query parameters, arbitrary hosts, authenticated endpoints
and inference endpoints are rejected. Known private-model flags reject the entire
API capture. Failed/incomplete staged sources cannot become successful captures.

## Corrections, retries and failure behavior

An explicit correction can be appended using `correct` with `--assertion-id`,
`--supersedes`, `--reason` and actual `--recorded-at`. Both assertions must already
exist, represent the same exact source-native identity/scope/type, and the
replacement must occur later in ledger order. Reverse/cyclic corrections and
cross-model aliases are rejected. Inspection returns both original assertions
and correction records; it does not silently choose a current price. A newer
capture is not automatically treated as a correction of an older valid price.

The separate `.ledger.lock` protects this warehouse. All new rows are checked
against their sources before any manifest commit. Immutable sources and bounded
segments are written first; the persisted candidate is then re-read and verified;
only then is the manifest atomically replaced and synced. A failure before that
point preserves the old committed ledger. Unreferenced staged files can remain
after an interruption; retries validate/reuse them and deduplicate record IDs.
There is no automatic pruning, source rewriting, Git-history rewrite or rewrite
of the original inventory-history migration archive.

Readers verify paths, symlinks, hashes, byte limits, schemas, unique IDs, counts,
record order, index witnesses and complete extraction. Every assertion and
capture-derived coverage record must match re-extraction from retained bytes with
its recorded `historical-native-v1` or `historical-native-v2` extractor. Standalone
v2 discovery checks validate exact public profiles and retained index witnesses;
they never create a source capture. A missing row, corrupt asset, invented value or unsupported
extractor fails the whole read; it never becomes an empty/partial successful
catalog. Future extractor versions must retain readers for older versions and
append corrected assertions rather than silently rewriting existing ones.

## Public boundary and validation

The explicitly authorized [historical dashboard projection](dashboard-data-organization.md#historical-public-projection)
reads and fully verifies the ledger, then publishes only selected historical fields
and bounded, validated chunks through `scripts/dashboard_projection.ts`. No raw
source, warehouse manifest or segment is copied into `dist/`. Calculators, reviewed
exports, current model listings and comparison charts do not consume this evidence.
Public repository files contain only the selected public historical evidence,
never collector credentials or authenticated responses.

Unit tests cover exact encoded-byte recovery, original dates/units/unknowns,
archive/AWS witnesses, private and ambiguous inputs, A → B → A preservation,
bounded segments, tampering/incomplete extraction, path/decompression attacks,
exclusive locking, interrupted manifest commits, retries, explicit corrections,
inspection and restore-without-overwrite. The public projection test also excludes
historical warehouse paths and raw-body assets.

For the initial import on 2026-10-26, local `npm run check` passed 98 frontend tests, 274 Python tests,
TypeScript and the production build. Full retained-source reconstruction passed;
re-importing the real batch changed no file bytes. Existing live-data files were
unchanged, and the built public assets contained no ledger manifest, segment or
source body. These are local checks, not hosted CI, a fresh collector run or a
deployment. Browser tests were not rerun because no UI behavior changed.
