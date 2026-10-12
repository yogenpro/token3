# Native history: reversible compaction and bounded storage

This is an explicitly authorized warehouse migration, **not** a dashboard build,
collector price update, new observation, or Git-history rewrite. It changes storage
and the interpretation of proven timestamp-only events, never quote eligibility.
Reviewed CSV/history, provider catalogs, source hashes and last-good state remain
unchanged.

## Why, and which observations qualify

The original `data/inventory_history.jsonl` was 100,067,786 bytes (95.43 MiB), close
to GitHub's 100 MiB per-file limit. Rolling Google Cloud Billing as-of timestamps
accounted for 45,728 repeated full Vertex record bodies. Keeping these observations
is important; treating them as new tariffs and duplicating their full state is not.

Only `vertex` `record_changed` events qualify when **both** the immediately previous
record state and the new state have:

- Historical catalog-SHA witnesses from retained Git catalog headers establishing
  verified HTTPS, unbounded latest SKU requests, without unknown query parameters.
- Exactly one valid pricing-info timestamp, matching rate timestamps and native
  service/SKU identity, using each state's own recorded `observed_at`.
- Identical canonical record content after excluding only the narrowly qualifying
  rolling timestamp fields. Amounts, currencies, units, scope, schedules, metadata
  and all other fields remain compared.

Unknown/missing historical request evidence, explicit ranges, multi-version
schedules, unconfirmed future times, other providers, discoveries, absences, notes,
real rate/rule changes and price reversions retain their original full events.
Past as-of anomalies are retained exactly; they are not fabricated tariff dates.
The source-specific contract remains in [collection retention](data-collection.md#google-latest-price-observations).

## Versioned layout

```text
data/inventory_history/manifest.json           ordered schema-1 warehouse manifest
data/inventory_history/segments/<sha>.jsonl.gz  immutable semantic/observation segments
data/inventory_history/archive/<sha>.jsonl.gz   immutable original migration ledger
data/inventory_history/proofs/<sha>.json        historical request-scope witnesses
```

The **warehouse** schema is separate from the public catalog delivery schemas.
Every gzip segment ends on a JSONL event boundary and is at most **16 MiB
uncompressed**. A single oversized event fails explicitly; it is never truncated.
References bind the exact safe path, compressed SHA-256/bytes, uncompressed
SHA-256/bytes, and event count. Segment order is explicit, not inferred from filenames
or dates. Month-only partitions would not bound large collection batches.

Full nonqualifying events retain their original JSON rows. A qualifying observation
keeps its original event ID, kind, record ID, revision, timestamps, catalog linkage
and every other event-level field, replacing only `after` with `_observation`:

- Policy version `google-unbounded-latest-v1`.
- Immediately preceding original event ID for the same retained record.
- Exact new source `effective_time`.
- SHA-256 of the original JSONL row, including its newline.

The Python and TypeScript readers reconstruct the original `after` body from that
state reference and exact timestamp. They return the original event plus a separate
verified observation-only flag; they do not silently rewrite its original `kind`.
Absence resets the retained state. Ordered replay, unique IDs, source-scope proofs,
hashes, bytes and counts are checked. Malformed/incomplete input fails closed.
The public change projection omits verified observation-only rows from tariff/rule
feeds. Other events retain their previous public IDs and values. Public provider
and record links are unchanged; original warehouse event IDs remain resolvable by
replay/archive. The dashboard has provider/record links, not independently addressable
legacy event-ID URLs. Its observation batches contain **change-bearing observations**,
not every successful daily check or compact as-of observation.

## Persistence and retries

Migration and collection share the exclusive `data/.collect.lock`; hosted collection
also retains Actions concurrency. Immutable assets are written first, their complete
archive/reconstruction is verified, then the manifest is atomically replaced as the
commit point. The legacy monolith is removed only after that point. If removal was
interrupted, rerunning the migration verifies the frozen original checksum before
removing the redundant copy. A changed legacy file is an error, not a second authority.

Future collector batches write new immutable segments, splitting oversized batches
at event boundaries, then atomically update the manifest **before** advancing catalogs.
There is no repeatedly rewritten unbounded active ledger. Small batches are sealed
immediately rather than accumulated into a mutable `active.jsonl`. Existing event IDs
are deduplicated on retries. A failed manifest commit leaves the previous history
readable and may leave harmless unreferenced staged assets; these are not published.
Legacy JSONL reading and bounded writing remain supported for older/small fixture
directories, but cannot silently grow a monolith beyond 16 MiB.

## Commands

Use the normal project Python environment on a Unix system supporting `flock`;
migration refuses to run without the exclusive lock. No provider, inference,
paid-service or external archive call is made by these commands.

```bash
# Read-only data report. Scope witnesses come from retained local Git headers.
python -m scripts.compact_inventory_history

# Explicit one-time migration; idempotent after successful verification.
python -m scripts.compact_inventory_history --apply

# Original archive checksum, original observation reconstruction, and all append totals.
python -m scripts.compact_inventory_history --verify

# Lossless original JSONL bytes at a NEW audit path; never overwrites existing output.
python -m scripts.compact_inventory_history --restore-archive /tmp/original-inventory-history.jsonl
```

The original migration requires sufficient local Git history for historical header
witnesses. A shallow clone may establish fewer candidates; missing evidence is
preserved, never inferred. The persisted proof artifact includes historical commit,
path/blob identity, catalog/source hashes, request scope and capture metadata. Normal
collection, builds, and verification read these checksummed artifacts and do not need
the historical Git objects. `--data-dir` permits isolated fixtures/audit directories.

## Audited migration snapshot

These counts are tied to input SHA-256
`bc83d5dee1eea18b355322e1b347cf439e7512e54da38ad9d0a19264064bb488`,
not permanent future totals:

| Measure | Result |
| --- | --- |
| Original observations/events | 71,879 |
| Verified compact as-of observations | 45,728 |
| Other full events | 26,151 |
| Compacted logical JSONL bytes | 56,609,937 (53.99 MiB, including observation metadata) |
| Immutable current segments | 4; 7.18 MiB compressed total |
| Lossless original archive segments | 6; 7.08 MiB compressed total |
| Total current + archive gzip storage | 14.26 MiB, plus a small manifest/proof |
| Public native amount events | 186, unchanged |
| Public billing-rule events | 45,896 → 168; only the 45,728 proven as-of rows removed |
| Public catalog events | 25,887, unchanged |

All 56 other production input files remained byte-identical. Every remaining public
event and all 133 baseline public provider/model/evidence assets remained identical.
Python and TypeScript replay recover every original event value and exact timestamp;
the archive reconstructs every original input byte and checksum. Tests cover genuine
changes/reversions, incomplete proofs, ambiguous scopes, malformed assets, UTF-8,
retry/commit failures and segment bounds. Builds remain read-only and never publish
warehouse segments, archives, proof files or authenticated response bodies.

### Release integration with newer collection

Before publication, scheduled collection commit
`29dbe855595e1874e06d59d648508ce856d53c5d` was fast-forwarded without rewriting
history. Its 45 new Hugging Face, Snowflake, OpenRouter and Scaleway native events
were appended unchanged into a fifth bounded segment. The original archive and
the audit snapshot above remain frozen; total native event count at integration
is 71,924, with the same 45,728 verified compact observations. Concatenating the
original archive bytes and this new segment reproduces the latest upstream
100,161,312-byte ledger exactly, SHA-256
`7690b7d8bc5c22d44510708be95fa968f92457382c0fce26bc4e88e4b35addee`.
`--restore-archive` intentionally restores the frozen original migration input,
not subsequent appends; ordered readers replay both. Every other production input
matches that newer collection commit. The release integration makes no new source
calls or fabricated observations. Deployment explicitly installs Python and its
requirements so its frontend suite can execute the actual Python-writer/TypeScript-
reader integrity fixtures rather than depend on incidental runner packages.

Compression and segmentation bound individual files, not total Git/repository growth.
Old 95 MiB Git blobs remain reachable in earlier commits. No LFS, database, history
rewrite or observation pruning is implied. Monitor manifest size, number of segments,
check-ledger growth and total Git size separately. Committing, pushing and deploying
this local migration require their own applicable authorization; the live Pages site
is not changed by this migration command.
