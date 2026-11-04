> ## Documentation Index
> Fetch the complete documentation index at: https://docs.perplexity.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Pricing

> Understand Perplexity API pricing, model rates, request fees, billing setup, and rate-limit references.

Each Perplexity API bills differently. The rates are in the sections below.

* **Orchestrator API:** per token, at each model's rates. No per-request fees. Requests rejected with a `429` are not billed.
* **Agent API:** per token, at each model's rates, plus tool fees. Most tools bill per call; `sandbox` bills per session, plus each SDK search query made inside it. The `flex` (0.5×) and `priority` (2×) service tiers change the token rates only for models that list that tier on the [Agent API Models page](https://docs.perplexity.ai/docs/agent-api/models.md). Other models always bill at the listed rate.
* **Search API:** per successful request.
* **Embeddings API:** per token.
* **Decisions API:** per input token. Output tokens are free.

For billing setup, payment methods, and usage monitoring, see the [Admin section](https://docs.perplexity.ai/docs/getting-started/projects.md). For rate limits, see [Rate Limits & Usage Tiers](https://docs.perplexity.ai/docs/admin/rate-limits-usage-tiers.md).

## Orchestrator API Pricing

Orchestrator API usage is billed per token at each model's published rates — there are no per-request fees. Every model has its own input and output rate, with cache reads billed at the model's discounted cache-read rate and reasoning tokens billed at the output rate. You are always billed at the requested model's rates, regardless of how the request is served.

See [Orchestrator Models & Pricing](https://docs.perplexity.ai/docs/router/models.md) for the full per-model rate card, including cache-read rates.

## Agent API Pricing

The Agent API provides access to third-party models from providers including OpenAI, Anthropic, Google, xAI, Z.AI, Moonshot AI, and NVIDIA with **transparent, token-based pricing** at each model's published rates.

### Model Pricing

Agent API pricing varies by provider and model, with each provider offering multiple models at different price points.

The input, output, and cache-read rate for each model is on the [Agent API Models page](https://docs.perplexity.ai/docs/agent-api/models.md).

### Tool Pricing

When using tools with the Agent API:

| Tool | Price | Description |
| - | :-: | - |
| **`web_search` (standard)** | \$0.0025 per invocation | Standard web search with `search_type: "web"`. \$2.50 per 1,000 invocations |
| **`web_search` (Fast Search)** | \$0.001 per invocation | The same tool with `search_type: "fast"`. \$1.00 per 1,000 invocations. See [Fast Search](https://docs.perplexity.ai/docs/search/fast-search.md) |
| **`image_search`** | \$0.0025 per successful invocation | Finds structured image results with domain, format, and safe-search filters. \$2.50 per 1,000 successful invocations |
| **`fetch_url`** | \$0.0005 per invocation | Fetches and extracts content from specific URLs |
| **`people_search`** | \$0.005 per invocation | Looks up professionals, employees, and people. \$5 per 1,000 tool invocations |
| **`finance_search`** | \$0.005 per invocation | Retrieves financial data and market information. \$5 per 1,000 tool invocations |
| **`sandbox`** | \$0.03 per session | Isolated container for executing code during an Agent API request. A session covers up to 20 minutes of active use for billing purposes — this is the billing window, not a runtime cap. SDK search queries made from inside the sandbox are billed at \$0.0025 per request (same as `web_search`). |

> [!NOTE]
>
> Most tool costs are per invocation. `sandbox` is billed per container session — a 20-minute billing window per container, not a runtime cap — plus per SDK search query made from inside it. Tool costs are separate from model token costs.

## Search API Pricing

| API | Price per 1K requests | Description |
| - | :-: | - |
| **Search API** | \$5.00 | Ranked web results as JSON, with page text extracted into each result's `snippet`. No model, no generated answer, no token billing. Filter by domain, language, and date, and bias results by country. |
| **Search API with [Fast Search](https://docs.perplexity.ai/docs/search/fast-search.md)** | \$1.00 | Lower-latency results in the same response format. Set `search_type: "fast"` |

> [!NOTE]
>
> **Billing unit:** Search API charges for each successful `POST /search` request, not for each query in the request. A successful request containing an array of up to five queries is one billing unit. Invalid requests, rate-limited requests, and upstream failures are not billed. A successful response is billed even when it returns no results. There are no additional token-based charges.

Search API cost = successful requests ÷ 1,000 × the price per 1K requests. The amount of extracted text (`max_tokens`, `max_tokens_per_page`) does not change the price.

| Request | Billing units | Cost |
| - | :-: | -: |
| One `POST /search` with one query, up to 20 results | 1 | \$5.00 ÷ 1,000 = \$0.005 |
| One `POST /search` with one query and `search_type: "fast"` | 1 | \$1.00 ÷ 1,000 = \$0.001 |
| One `POST /search` with a `query` array of five queries | 1 | \$0.005 (standard) or \$0.001 (Fast Search) |
| 10,000 successful standard requests in a month | 10,000 | 10 × \$5.00 = \$50.00 |

What a result contains, the request controls, and the limits on queries, results, and extracted text are in the [Search API overview](https://docs.perplexity.ai/docs/search/overview.md).

## Embeddings API Pricing

Generate high-quality text embeddings for semantic search, retrieval-augmented generation (RAG), and other machine learning applications.

### Standard Embeddings

| Model | Dimensions | Price (\$/1M tokens) |
| - | :-: | :-: |
| `pplx-embed-v1-0.6b` | 1024 | \$0.004 |
| `pplx-embed-v1-4b` | 2560 | \$0.03 |

### Contextualized Embeddings

| Model | Dimensions | Price (\$/1M tokens) |
| - | :-: | :-: |
| `pplx-embed-context-v1-0.6b` | 1024 | \$0.008 |
| `pplx-embed-context-v1-4b` | 2560 | \$0.05 |

Embeddings cost = tokens ÷ 1,000,000 × the model's rate. For example, 40M tokens on `pplx-embed-context-v1-4b` cost 40 × \$0.05 = \$2.00.

To use the Embeddings API, see the [Embeddings quickstart](https://docs.perplexity.ai/docs/embeddings/quickstart.md).

## Decisions API Pricing

The Decisions API answers yes/no, multiple-choice, and scored questions about text and images with calibrated probabilities.

| Model | Price (\$/1M input tokens) | Output tokens | Per-request fee |
| - | :-: | :-: | :-: |
| `pplx-decider-v1.2` | \$0.02 | Free | None |
| `pplx-decider-flash-v1.2` | \$0.01 | Free | None |

> [!NOTE]
>
> **Aliases:** `pplx-decider-latest` and `perplexity/pplx-decider-latest` select `pplx-decider-v1.2`. `pplx-decider-flash-latest` and `perplexity/pplx-decider-flash-latest` select `pplx-decider-flash-v1.2`. An alias bills at the rate of the model it selects. Requests that name `pplx-decider-v1.1-27b` or `pplx-decider-v1-27b` select `pplx-decider-v1.2` and bill at \$0.02.
>
> **Billing unit:** you pay for input tokens only. The `state`, every question, and any images count as input; the response reports the exact number as `usage.input_tokens`, so you can compute the cost of a request from the response you already receive. A request with 600 input tokens costs \$0.000012 on `pplx-decider-v1.2` and \$0.000006 on `pplx-decider-flash-v1.2`.

To use the Decisions API, see the [Decisions quickstart](https://docs.perplexity.ai/docs/decisions/quickstart.md).

Token counts: 1 token is about 4 characters of English text. The exact count varies with language and content.

## Cost Examples

To estimate an Agent API request, add these parts:

* uncached input tokens × the model's input rate ÷ 1,000,000
* cached input tokens × the model's cache-read rate ÷ 1,000,000
* output tokens × the model's output rate ÷ 1,000,000. The response reports reasoning tokens in `usage.output_tokens_details.reasoning_tokens`; the Models page notes where they bill at the output rate.
* the price of each tool call (from the Tool Pricing table)
* \$0.03 per `sandbox` session, plus \$0.0025 per SDK search query made inside it

Model rates are per 1M tokens, on the [Agent API Models page](https://docs.perplexity.ai/docs/agent-api/models.md). Where a rate lists a context-length range, use the rate that matches the request's input size. With `flex` or `priority` on a model that lists that tier, multiply the token cost by 0.5 or 2. Tool fees don't change.

Actual effort level costs vary with the selected model, token usage, and tool invocations. When present on a completed response, `usage.cost.total_cost` reports the calculated request cost.

## Purchase Options

* [Perplexity API Platform on AWS Marketplace](https://docs.perplexity.ai/docs/resources/aws-marketplace.md): buy API credits through AWS Marketplace with consolidated billing and enterprise procurement.
* [Contact the sales team](https://perplexity.typeform.com/to/m3WnMaG6): ask about custom pricing, dedicated support, and enterprise features.
