# Pricing and rate limits

Use our models with pay-as-you-go billing on Meta Model API and in [Muse Code](https://dev.meta.ai/docs/muse-code), or in Muse Code with a monthly [subscription](https://dev.meta.ai/docs/muse-code/subscriptions). This page covers pay-as-you-go: Model API bills text models per token, image generation per image, Muse Voice Transcribe by the hour of audio processed, and Segment Anything Model (SAM) per image or video frame segmented, with no minimums or upfront commitment.

## Pricing modes

Some models can be used in two modes. Standard mode uses standard pricing. Contributor mode offers discounted pricing or more usage in exchange for permission to use your content — the prompts, code, files, and context you send, plus the model responses you get back — to train future Meta models.

### Standard mode

In Standard mode, you pay standard prices and your content is not used to train Meta models. Every model on this page is available in Standard mode.

### Contributor mode

On Model API, Contributor mode runs the same models at heavily discounted token prices, in exchange for permission to use your content to train future Meta models. It lowers the barrier to entry for prototyping, testing integrations, and scaling experiments where it's acceptable for Meta to use your content to train future Meta models.

On Model API, use Contributor mode with Muse Spark 1.3 or 1.2 by calling its Contributor-mode variant: `muse-spark-1.3-contributor` or `muse-spark-1.2-contributor`. Contributor mode isn't available for Muse Wonder on Model API.

In [Muse Code](https://dev.meta.ai/docs/muse-code), subscriptions default to Contributor mode, and you can turn it on or off in settings; see [Contributor mode in Muse Code](https://dev.meta.ai/docs/muse-code/subscriptions#contributor-mode).

## Model pricing

### Muse Wonder

Model: `muse-wonder-1.0`.

| Usage        | Standard mode (per 1M tokens) | Contributor mode (per 1M tokens) |
| :----------- | :---------------------------- | :------------------------------- |
| Cached input | $0.20                         | Not available                    |
| Input        | $4.00                         | Not available                    |
| Output       | $20.00                        | Not available                    |

### Muse Spark

Models: `muse-spark-1.3`, `muse-spark-1.2`, and `muse-spark-1.1` in Standard mode; `muse-spark-1.3-contributor` and `muse-spark-1.2-contributor` in Contributor mode. Muse Spark 1.1 is Standard mode only.

| Usage        | Standard mode (per 1M tokens) | Contributor mode (per 1M tokens) |
| :----------- | :---------------------------- | :------------------------------- |
| Cached input | $0.15                         | $0.002                           |
| Input        | $1.25                         | $0.10                            |
| Output       | $4.25                         | $0.20                            |

### Token pricing notes

These apply to the token-priced models above, Muse Wonder and Muse Spark.

- **Cached input costs less**: When part of your prompt matches a [cached prefix](https://dev.meta.ai/docs/prompt-caching), you pay the cached-input rate for those tokens. Check `cached_tokens` in the response to see how many were served from cache.
- **No long-context premium**: you pay the same rate whether your context window is mostly empty or almost full.
- **Web search grounding**: **$2.50 per 1,000 search queries**, in addition to the request's token cost. This applies to the [`web_search` tool](https://dev.meta.ai/docs/search-grounding) on text models such as [Muse Wonder](https://dev.meta.ai/docs/models#muse-wonder) and [Muse Spark](https://dev.meta.ai/docs/models#muse-spark).

> **NOTE: Muse Image search is included**
>
> [Muse Image](https://dev.meta.ai/docs/models#muse-image)'s built-in web and image search is part of its per-image price and isn't charged separately. See [Muse Image pricing](https://dev.meta.ai/docs/pricing-rate-limits#image-generation).
