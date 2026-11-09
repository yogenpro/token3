<!-- Public source excerpt: https://dev.meta.ai/docs/pricing-rate-limits.md
Captured by run 42653560204 on 2026-11-09; Standard/Contributor columns reordered. -->

## Model pricing

### Muse Wonder

Model: `muse-wonder-1.0`.

| Usage        | Contributor mode (per 1M tokens) | Standard mode (per 1M tokens) |
| :----------- | :------------------------------- | :---------------------------- |
| Cached input | Not available                    | $0.20                         |
| Input        | Not available                    | $4.00                         |
| Output       | Not available                    | $20.00                        |

### Muse Spark

Models: `muse-spark-1.3`, `muse-spark-1.2`, and `muse-spark-1.1` in Standard mode; `muse-spark-1.3-contributor` and `muse-spark-1.2-contributor` in Contributor mode. Muse Spark 1.1 is Standard mode only.

| Usage        | Contributor mode (per 1M tokens) | Standard mode (per 1M tokens) |
| :----------- | :------------------------------- | :---------------------------- |
| Cached input | $0.002                           | $0.15                         |
| Input        | $0.10                            | $1.25                         |
| Output       | $0.20                            | $4.25                         |

### Token pricing notes

These apply to the token-priced models above, Muse Wonder and Muse Spark.

- **Cached input costs less**: When part of your prompt matches a [cached prefix](https://dev.meta.ai/docs/prompt-caching), you pay the cached-input rate for those tokens. Check `cached_tokens` in the response to see how many were served from cache.
- **No long-context premium**: you pay the same rate whether your context window is mostly empty or almost full.
- **Web search grounding**: **$2.50 per 1,000 search queries**, in addition to the request's token cost. This applies to the [`web_search` tool](https://dev.meta.ai/docs/search-grounding) on the reasoning models, [Muse Wonder](https://dev.meta.ai/docs/models#muse-wonder) and [Muse Spark](https://dev.meta.ai/docs/models#muse-spark).

> **NOTE: Muse Image search is included**
>
> [Muse Image](https://dev.meta.ai/docs/models#muse-image)'s built-in web and image search is part of its per-image price and isn't charged separately. See [Muse Image pricing](https://dev.meta.ai/docs/pricing-rate-limits#image-generation).
