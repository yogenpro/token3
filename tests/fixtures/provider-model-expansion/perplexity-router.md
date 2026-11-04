> ## Documentation Index
> Fetch the complete documentation index at: https://docs.perplexity.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Orchestrator Models & Pricing

> The model catalog for the Perplexity Orchestrator API, with per-token pricing for Perplexity-hosted and third-party models.

> [!NOTE]
>
> Orchestrator API is in private preview. Email [api@perplexity.ai](mailto:api@perplexity.ai) to request access.

## Overview

Every model below is available through both Orchestrator API endpoints — [Chat Completions](https://docs.perplexity.ai/api-reference/gateway-chat-completions-post.md) and [Messages](https://docs.perplexity.ai/api-reference/gateway-messages-post.md) — under the same `creator/model-name` id. Prices are in USD per 1 million tokens, and you are billed at the requested model's rates regardless of how the request is served.

For the live catalog, query [`GET /models`](https://docs.perplexity.ai/api-reference/gateway-models-get); the tables below show the current catalog.

> [!NOTE]
>
> Cached input is billed separately from fresh input: cache reads are billed at the discounted per-model rate shown in the "Cache read" column, and cache writes at the rate shown (or at the input rate where no dedicated write rate is listed). Reasoning tokens are billed at the output rate.
>
> `perplexity/glm-5.3-flash` supports cache reads but not cache writes.

## Perplexity-Hosted Models

Open-source models hosted by Perplexity — the `perplexity/` prefix reflects who serves the model, not who created it. The catalog includes models from DeepSeek, Moonshot AI, and Z.AI:

| Model | Input (\$/1M) | Output (\$/1M) | Cache read (\$/1M) | Docs |
| - | -: | -: | -: | - |
| **`perplexity/kimi-k3`** | 3.00 | 15.00 | 0.30 | [Kimi K3](https://huggingface.co/moonshotai/Kimi-K3) |
| **`perplexity/glm-5.3`** | 1.40 | 4.40 | 0.26 | [GLM](https://docs.z.ai) |
| **`perplexity/glm-5.3-flash`** | 0.15 | 0.50 | 0.03 | [GLM-5.3 Flash](https://huggingface.co/zai-org/GLM-5.3-Flash) |
| **`perplexity/deepseek-v4-pro-0813`** | 1.32 | 3.96 | 0.044 | — |

## Listing Models Programmatically

```bash theme={null}
curl 'https://api.perplexity.ai/orchestrator/v1/models' \
  -H "Authorization: Bearer $PERPLEXITY_API_KEY" | jq
```

The response lists every available model sorted by id, including each model's base token prices. Requesting a model that is not in the catalog returns a `400` naming the invalid model — the catalog is also the allowlist.

## Next Steps

> [card] [Quickstart](https://docs.perplexity.ai/docs/router/quickstart.md)
>
> Make your first Orchestrator API call.

> [card] [Pricing & Billing](https://docs.perplexity.ai/docs/getting-started/pricing.md)
>
> How credits, billing, and usage tiers work across the platform.
