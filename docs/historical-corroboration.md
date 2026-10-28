# Best-effort historical pricing corroboration

On 2026-10-26 the user explicitly accepted best-effort accuracy for historical
prices and authorized corroboration with news reports and social posts. This
widens the research evidence boundary; it does not authorize invented observations,
amounts, effective dates, model aliases or comparable current quotes.

The original [historical ledger](historical-evidence-ledger.md) continues to retain
exact public archive bytes with index/digest witnesses, immutable segments and
append-only corrections. It is not rewritten to make historical reports look
like contemporaneous native captures.

## Report catalog

`catalog/historical_reports.json` is a separate curated research input, validated
by `scripts/historical_reports.py`. Each source records its public URL, publisher,
source class, explicit publication day, actual retrieval day/timezone, short exact
excerpt and SHA-256 of those excerpt bytes. The excerpt is at most 25 words;
neither the excerpt hash nor a search result is presented as a full-page capture.
The file does not redistribute whole news articles or social threads.
The pages were read during this research pass and may have been edited since
their reported publication dates; no contemporaneous archive capture is inferred.

Source classes distinguish provider announcements/documents, provider social posts, news
reports and community social posts. Provenance groups prevent a provider release
and articles repeating it from being described as independent measurements.
Unretrieved social links are explicit leads with `supports_pricing: false`.

Claims preserve the published model label; an exact native API ID can remain
unknown. Original decimal amounts, units, currency symbols, unknown ISO currency,
region/tier/flavor uncertainty and notes stay explicit. Publication/reported days
do not become tariff-effective timestamps. An effective day needs an explicit billing-start/effective-date statement in a
retained excerpt and its source ID; no midnight or timezone is invented. Dollar
symbols do not establish an ISO currency. All claims remain
`best_effort_historical` and `comparison_eligible: false`.

Confidence labels are `provider_reported`,
`provider_reported_with_secondary_coverage`, `single_report` and
`conflicting_reports`. Conflicts require reciprocal references to both retained
claims; the validator rejects silently dropping the conflict or promoting a claim.

The initial batch retained eight claims from seven sources. The catalog now
retains ten claims from nine sources, including two additional provider reports:

- xAI's dated December 2024 announcement names `grok-2-1212` and
  `grok-2-vision-1212`, with reported token amounts. TestingCatalog separately
  covers the announcement. This is secondary coverage of the same announcement,
  not two independent price measurements.
- An October 2024 TechCrunch report and a November 2024 InfoQ report describe
  older `grok-beta` amounts with conflicting input denominators. Both remain
  attributed and unresolved. Different dates and different model IDs are not
  silently converted into a same-SKU tariff change.
- Nebius's November 2024 release reports Llama 3.1 405B pricing while quoting an
  Artificial Analysis representative. This is retained as a provider report,
  not independently retained benchmark evidence. Exact API identity and flavor
  remain unresolved.
- Microsoft’s March 2023 Azure announcement supplies separate GPT-4 8k/32k
  rates and an explicit April 1 billing-start day, retained at day precision.
- Microsoft's May 2024 GPT-4o announcement supplies input/output amounts and
  explicitly warns that pricing is subject to change starting May 24. The report
  does not infer a later tariff or a continuous effective interval.
- Nebius's January 27, 2025 DeepSeek R1 article supplies an input-token amount;
  output pricing, exact API ID and flavor remain unknown. Later social-post
  dates do not replace the provider article's publication day.
- Oracle’s July 2024 article supplies Llama 3 shared-service rates per 10,000
  characters. These are not converted to tokens or mapped to an unstated model size.
- The social announcement linked from the October report could not be retrieved
  directly (HTTP 403). It is a lead, not numeric-price corroboration.

The catalog currently feeds research/coverage reporting only. It is outside the
dashboard's public allowlist, reviewed exports and current comparisons. A public
report UI would need its own explicit field projection and schema; this data pass
does not publish a code release.

## Licensed community history datasets

The [community dataset report](research/historical-recovery-community-2026-10-26.json)
retains two additional sources at exact Git commit SHAs: Llerandi's
`llm-price-tracker` (MIT, full copyright/license notice retained) and
`romanshumy/llm-prices-data`, attributed to **modelpricewatch.com** under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Exact dataset, README
and license bytes are retained as checked gzip research assets. These are separate
publisher reports, not additions to the provider-native ledger or public app.

At this retrieval, the former has 64 model records and 5,824 publisher-dated
entries from July 28–October 26, 2026. The latter has 313 model records and 23,245
publisher-dated entries spanning February 5, 2024–October 27, 2026. These include
source labels outside the 26 tracked groups. Repeated daily values are not counted
as distinct price changes, and dates may be retrospective publisher claims.
This does not independently verify when the publisher or vendor observed a price.

Source-local model keys and provider labels remain verbatim. Labels such as
`Google`, `Amazon` or `Qwen` do not establish a billing source or canonical/native
identity. No Gemini/Vertex merge, new Qwen billing provider, currency conversion,
native-ID inference or reviewed quote is created. Native provider/ID fields stay
unknown; all records are `unreviewed_community_report` and comparison-ineligible.
The coverage audit continues to grade native/document/PDF evidence separately.

Use this explicit command to validate a staged source/license bundle:

```bash
python -m scripts.historical_community_research \
  --stage-dir /path/to/stage --output /path/to/report.json
```

It rejects byte/hash changes, mixed commits, absent licenses and misaligned
date/amount arrays before writing research assets. Retrieval does not run remote
repository code or install its dependencies.

## Prices published as images

The [visual price report](research/historical-recovery-image-prices-2026-10-27.json)
retains three exact pricing-table images, their source URLs/hashes, parent
announcement publication days and actual 2026 retrieval timestamps. Nine
best-effort transcriptions preserve sixteen amount expressions. These are
separate research reports; they are not native observations or public app assets.

Google's December 2023 Gemini Pro chart quotes characters and images, not tokens,
and the article describes a future paid tariff following free preview access.
Its April 2025 Gemini 2.5 Pro chart distinguishes two bands and includes reasoning
tokens in output; experimental/free and paid-preview variants are not merged.
Neither announcement supplies an inferred tariff-effective timestamp or exact API ID.

Fireworks' March 2024 chart reports previous input/output amounts and new flat
amounts for parameter buckets and Mixtral. The prior interval is unknown, and the
new column omits its denominator even though adjacent previous-price columns say
per million tokens. That ambiguity stays explicit. The billing-rule change is
not converted into a same-basis amount-change event or a canonical model mapping.
Image publication/continuity is unverified: a dated parent article does not prove
these exact image bytes were present on its original publication day.

## Pricing coverage versus document coverage

`scripts/historical_price_coverage.py` reconstructs the ledger and reports all
currently indexed provider groups. It distinguishes structured native amounts,
heuristic numeric candidates in aligned price columns, attributed report claims,
and cases where no numeric historical price has been identified.

The audit does not count model-ID digits, context limits, retirement dates,
discount percentages alone, dynamic-price sentinels or missing amounts as prices.
Document candidates are leads for review, not verified model-to-rate mappings.
Unaligned PDF/narrative text is not automatically promoted into structured rates.
Counts include repeated captures and non-token billing; they are not unique model,
token-tariff or price-change counts.

The audit records retained assertion/capture IDs and source/date witnesses for
examples. Outstanding archive targets subtract subsequently imported successes
while preserving original failed/deferred coverage checks. A zero outstanding
count applies only to selected indexed URLs, not all provider history.

```bash
python -m scripts.historical_reports
python -m scripts.historical_price_coverage \
  --output /tmp/historical-price-coverage.json
python -m unittest discover -s tests -p 'test_historical*.py' -v
```

Historical recovery remains manual and source-bounded. No paid/authenticated
history source, inference request, automatic daily raw retention or new website
release is authorized by this research policy.

## Archive decoding research

The [target recovery](historical-target-recovery.md) adds derivative decoding of
already retained exact source bytes. These reports remain separate from native
assertions, reviewed quotes and public dashboard assets:

- Azure `data-amount` expressions preserve regional maps, raw decimal expressions,
  source row/column labels and unknowns behind visible placeholders. Table-local
  ambiguity or spanning cells cannot establish a model/column binding. No unit,
  model version, region equivalence or ISO currency is filled in by inference.
- DeepInfra's selected `__NEXT_DATA__` paths retain explicit model identifiers,
  original pricing objects and section conditions, including non-token units.
  Relative cache/discount factors alone are not counted as absolute amounts.
  Private model entries and vendor quality/throughput figures are excluded from
  derivative model candidates. JSON is parsed as data, never executed as JavaScript.
- Snowflake Table 6(a) research requires explicit unit headings and aligned
  single amounts, or explicit Input/Output headings for paired amounts. It retains
  original feature text, attached footnote markers, legacy labels and source lines.
  Credit units are not converted to currency, and page continuations do not supply
  inferred API IDs, release dates or tariff start dates. Complete footnotes and
  conditions remain available in the original retained PDF.
- Other previously unparsed document encodings are retried as bounded Brotli,
  explicit UTF-16 BOMs or a small allowlist of source-declared HTML charsets.
  Decoded aligned rows retain original identifiers, headers and source expressions;
  failed decoding remains unknown, and no native capture is reclassified.

The source-native ledger is unchanged by decoding. A Brotli-encoded source can
remain native-unparsed while derivative research uses the pinned
[Brotli 1.2.1 decoder](https://github.com/google/brotli/releases/tag/v1.2.1) with an
output bound of 16 MiB. Decoded content never replaces its encoded source bytes.
Every derivative candidate remains comparison-ineligible and explicitly unreviewed.

The same derivative readers accept separately witnessed Arquivo.pt captures.
They preserve the actual archive URL, source hash and capture time; a capture from
one archive cannot supply the date or digest of a missing capture from another.
See the [archive recovery method and remaining gaps](historical-target-recovery.md).

Large derivative reports use immutable SHA-256-addressed gzip segments capped at
16 MiB uncompressed and an atomic manifest capped at 4 MiB. Use
`scripts.historical_research_files.read_report` to reconstruct them; it verifies
paths, hashes, byte bounds, segment ordering and complete counts. Small reports
remain inline. These research files are outside the app's publication allowlist.

`scripts.historical_research_pipeline` validates one exact ledger snapshot and
shares those validated rows across the sibling audits. Its price audit independently
reconstructs PDF/embedded candidates from the retained source bytes before counting
them. The snapshot hash binds the manifest bytes read before validation, even if
a later atomic append advances the live manifest. No source verification is skipped.
