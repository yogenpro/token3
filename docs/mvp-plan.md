# LLM Inference Pricing Dashboard — MVP Plan

## Goal

Build a small dashboard that answers:

> **For the same model, what are different providers charging right now, and how has that pricing changed over time?**

This is an observation and analysis project. It is **not** a router, gateway, FinOps product, or startup thesis at this stage.

The dashboard should make it easy to:

- select a model;
- see all providers offering that model;
- compare input/output/cache pricing;
- inspect relevant offering differences;
- see which provider is cheapest for a chosen token mix;
- view price history over time;
- notice when providers add/remove a model or change pricing.

---

## 1. MVP scope

### In scope

- Same-model price comparison across providers.
- Current input/output token pricing.
- Cache read/write pricing when applicable.
- Basic offering metadata:
  - provider;
  - provider model ID;
  - context window;
  - quantization / precision when known;
  - region or service tier when pricing differs.
- Historical price observations.
- Simple workload-cost calculator.
- Charts showing price changes.
- Source URL and observation timestamp for every price.

### Out of scope for now

- Live request routing.
- BYOK.
- Customer-specific negotiated prices.
- Cloud commitments and credits.
- Latency / throughput benchmarking.
- Reliability / SLA optimization.
- Rate-limit-aware routing.
- Billing integrations.
- Enterprise policy / compliance.
- Market sizing or startup validation.

These can be revisited only if the dashboard itself becomes useful enough to justify them.

---

## 2. Core data model

The important distinction is between a **model** and a **provider offering** of that model.

### `models`

```text
id
creator
name
version
family
open_weight
```

Example:

```text
meta/llama-3.3-70b-instruct
```

### `offerings`

```text
id
model_id
provider
provider_model_id
context_window
quantization
service_tier
region
source_url
active
```

Example:

```text
model_id: meta/llama-3.3-70b-instruct
provider: fireworks
provider_model_id: accounts/fireworks/models/llama-v3p3-70b-instruct
quantization: fp8
```

### `price_history`

Append-only:

```text
offering_id
observed_at
input_per_million
output_per_million
cache_read_per_million
cache_write_per_million
currency
source_url
```

Do not overwrite old prices.

If today's price is unchanged, either:

1. record another daily observation; or
2. record only changes and keep `valid_from` / `valid_until`.

For the MVP, daily observations are simpler and the dataset will still be tiny.

---

## 3. Model equivalence

This is the only part worth being slightly careful about.

Provider names may look like:

```text
meta-llama/Llama-3.3-70B-Instruct
llama-3.3-70b
meta/llama-3.3-70b-instruct
llama-3.3-70b-instruct-fp8
```

Normalize them to a canonical model ID.

But do **not** hide meaningful differences.

Keep fields such as:

```text
quantization
context_window
service_tier
```

So the UI can say:

```text
Llama 3.3 70B Instruct

Provider       Input       Output      Variant
------------------------------------------------
A              $0.20       $0.60       FP8
B              $0.25       $0.70       unspecified
C              $0.35       $0.80       FP16
```

The dashboard does not need to decide whether FP8 and FP16 are perfectly interchangeable. It merely needs to make the difference visible.

A lightweight manual alias file is enough:

```yaml
meta/llama-3.3-70b-instruct:
  aliases:
    - meta-llama/Llama-3.3-70B-Instruct
    - llama-3.3-70b
    - meta/llama-3.3-70b-instruct
```

No elaborate equivalence engine is needed initially.

---

## 4. Dashboard views

### A. Model comparison page

This is the main page.

```text
Llama 3.3 70B Instruct

Provider     Input/M    Output/M    Cache/M    Context    Variant
------------------------------------------------------------------
Provider A    $0.10       $0.40      $0.05       128K       FP8
Provider B    $0.14       $0.35      —           128K       FP8
Provider C    $0.25       $0.80      —           128K       FP16
```

Useful controls:

```text
[Model selector]
[Input tokens]
[Output tokens]
[Cache hit %]
```

Then calculate:

```text
Estimated cost per request
Estimated cost per 1M requests
Cheapest provider for this workload
```

This is analysis only; it does not send requests anywhere.

### B. Price-history chart

For a selected model:

```text
$/1M tokens

0.8 |                 Provider C
    |                 ──────────
0.6 |
    | Provider B ───────────────
0.4 |
    |      Provider A
0.2 | ──────────────────────────
    |
    +--------------------------------
      Jan     Feb     Mar     Apr
```

Allow toggling:

```text
input price
output price
cache read price
```

### C. Recent changes

A very useful simple page:

```text
2026-10-02
Provider A cut Model X output price:
$0.80 -> $0.60 (-25%)

2026-09-29
Provider B added Model Y.

2026-09-27
Provider C increased Model Z input price:
$0.10 -> $0.12 (+20%)
```

This makes the project interesting even without any routing functionality.

### D. Model overview

Optional:

```text
Model                     Providers    Cheapest input    Cheapest output
-----------------------------------------------------------------------
Llama X                       12            $0.10             $0.30
Qwen Y                         9            $0.08             $0.25
Model Z                        4            $0.50             $1.50
```

---

## 5. Data collection

Start small.

Choose perhaps:

- 5–10 models;
- 5–10 providers;
- only models that appear on multiple providers.

Do not try to cover the whole market immediately.

### Source preference

Use:

1. official pricing API, if available;
2. official provider pricing/model page;
3. official documentation;
4. manual entry if necessary.

Other aggregators can be used to discover discrepancies, but keep the original provider page as the source attached to your data.

### Collector output

Each provider collector can emit something like:

```json
{
  "provider": "example",
  "provider_model_id": "llama-3.3-70b",
  "input_per_million": 0.20,
  "output_per_million": 0.60,
  "cache_read_per_million": null,
  "context_window": 131072,
  "quantization": "fp8",
  "source_url": "https://...",
  "observed_at": "2026-10-03T12:00:00Z"
}
```

A normalization step maps the provider model ID to the canonical model.

---

## 6. Simple architecture

For this scope, a backend service is unnecessary.

A nice low-maintenance architecture is:

```text
                  GitHub Actions
                       |
                   daily cron
                       |
                       v
              Python collectors
                       |
                       v
                normalized data
                CSV / JSON / Parquet
                       |
                       v
                   Git repo
                       |
                       v
                static dashboard
                       |
                       v
                 GitHub Pages
```

This has several advantages:

- nearly free;
- no server to maintain;
- Git itself gives another audit trail;
- pull requests can review suspicious price changes;
- easy to add providers incrementally.

### Suggested repository

```text
llm-price-watch/
├── README.md
├── providers/
│   ├── provider_a.py
│   ├── provider_b.py
│   └── provider_c.py
│
├── catalog/
│   ├── models.yaml
│   └── aliases.yaml
│
├── data/
│   ├── offerings.json
│   ├── latest_prices.json
│   └── price_history.csv
│
├── scripts/
│   ├── collect.py
│   ├── normalize.py
│   └── detect_changes.py
│
├── dashboard/
│   └── ...
│
└── .github/
    └── workflows/
        ├── collect.yml
        └── deploy.yml
```

---

## 7. Storage

Do not over-engineer this.

For the first version:

```text
catalog          -> YAML
current state    -> JSON
history          -> CSV or Parquet
```

That may be all that is needed.

If queries become inconvenient later, load the same files into DuckDB.

A hosted Postgres database is unnecessary for the initial dashboard.

---

## 8. Price-change detection

After every collection run:

```python
previous = latest_price(offering)
current = collected_price(offering)

if current != previous:
    append_change_event(previous, current)
```

Generate:

```text
changes.json
```

Example:

```json
{
  "date": "2026-10-03",
  "model": "model-x",
  "provider": "provider-a",
  "field": "output_per_million",
  "old": 0.80,
  "new": 0.60,
  "change_pct": -25
}
```

This can power the "Recent changes" page.

---

## 9. Workload calculator

A small calculator makes raw prices much easier to interpret.

Inputs:

```text
input tokens
output tokens
cached input tokens
number of requests
```

Calculation:

```text
cost =
    input_tokens × input_rate
  + output_tokens × output_rate
  + cached_tokens × cache_rate
```

Run it against every provider offering for the selected model.

Display:

```text
Provider A     $12.40
Provider B     $15.10
Provider C     $21.80
```

This avoids inventing a universal "blended price."

---

## 10. First milestone

The first useful milestone can be very small:

### Models

Pick approximately 5 popular models that are available through multiple providers.

### Providers

Add approximately 5–8 providers that collectively cover those models.

### Features

- [ ] model selector;
- [ ] current provider price table;
- [ ] source links;
- [ ] observation timestamps;
- [ ] input/output/cache comparison;
- [ ] simple workload calculator;
- [ ] daily historical collection;
- [ ] line chart for price history;
- [ ] recent price-change feed.

That's enough to answer the original question well.

---

## 11. What to learn from it

Once it has accumulated data, simply observe:

- Which models have the widest price spreads?
- Are open-weight models priced more competitively?
- Which providers tend to be cheapest?
- How often do prices actually change?
- Do providers quickly match price cuts?
- Does price dispersion shrink as a model gets older?
- Are input and output prices competed differently?
- How much does cache pricing change the ranking?
- Do new providers enter at lower prices?

There is no need yet to translate any of this into a business thesis.

The dataset itself is the experiment.

---

## 12. Possible future extensions

Only add these if they become interesting:

```text
latency measurements
throughput measurements
availability checks
provider regions
batch pricing
context-based price tiers
API compatibility details
release dates
price-drop notifications
RSS feed
public API
```

And much later, if the data naturally suggests it:

```text
routing
```

But routing does not need to influence the architecture now.

---

## 13. Recommended philosophy

Optimize for:

```text
small
transparent
auditable
historical
easy to extend
```

rather than:

```text
comprehensive
real-time
enterprise-ready
automatically intelligent
```

A useful first version is essentially:

> **PCPartPicker / CamelCamelCamel for LLM inference prices, organized around the canonical model.**

That is a clean project on its own.
