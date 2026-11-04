> ## Documentation Index
> Fetch the complete documentation index at: https://docs.perplexity.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Agent API Models

> Compare Agent API models, token pricing, supported service tiers, and provider documentation.

> [!NOTE]
>
> Looking for ranked web results instead of a generated answer? Use the Search API at `POST /search`. It takes no `model` parameter and bills per successful request, not per token. Start with the [Search API quickstart](https://docs.perplexity.ai/docs/search/quickstart.md).

## Available Models

The Agent API provides a unified interface to models from multiple providers with transparent token-based pricing.

Pricing rates are published per model and may differ from provider list prices. All charges are based on actual token consumption, and every API response includes exact token counts so you know your costs per request.

The **Service tiers** column lists optional non-default tiers. An em dash means the model uses default processing only.

A rate with a context-length range, such as `(≤272k)`, changes when the input is above that range. A single value applies at every context length.

> [!TIP]
>
> Looking for pre-configured model setups? See [**Effort Levels**](https://docs.perplexity.ai/docs/agent-api/effort.md) — optimized for specific use cases.

> [tab] Anthropic
>
> > [card] Anthropic
> >
> > Claude Opus (highest reasoning), Sonnet (balanced), and Haiku (fastest, cheapest).
>
> | Model | Input (\$/1M) | Output (\$/1M) | Cache read (\$/1M) | Service tiers | Docs |
> | - | - | - | - | - | - |
> | `anthropic/claude-fable-5` | 10.00 | 50.00 | 1.00 | — | [Claude Fable 5](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5) |
> | `anthropic/claude-fable-5-1` | 10.00 | 50.00 | 0.25 | — | [Claude Fable 5.1](https://platform.claude.com/docs/en/about-claude/models/overview) |
> | `anthropic/claude-opus-5-5` | 4.00 | 20.00 | 0.20 | — | [Claude Opus 5.5](https://platform.claude.com/docs/en/about-claude/models/overview) |
> | `anthropic/claude-opus-5` | 5.00 | 25.00 | 0.50 | — | [Claude Opus 5](https://platform.claude.com/docs/en/about-claude/models/overview) |
> | `anthropic/claude-sonnet-5-5` | 2.00 | 10.00 | 0.10 | — | [Claude Sonnet 5.5](https://www.anthropic.com/claude-sonnet-5-5) |
> | `anthropic/claude-sonnet-5` | 2.00 | 10.00 | 0.20 | — | [Claude Sonnet 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-sonnet-5) |
> | `anthropic/claude-haiku-5-5` | 0.10 (≤100k) 0.50 (>100k) | 0.50 (≤100k) 2.50 (>100k) | 0.01 (≤100k) 0.05 (>100k) | — | [Claude Haiku 5.5](https://platform.claude.com/docs/en/about-claude/models/overview) |
>
> > [!WARNING]
> >
> > Requests that use an `anthropic/*` model must include `max_output_tokens`. If omitted, the API returns HTTP 400 with `validation failed: max_output_tokens is required when using Anthropic models`. `max_output_tokens` is a shared Agent API parameter, but this required condition applies only to Anthropic models.

> [tab] OpenAI
>
> > [card] OpenAI
> >
> > OpenAI GPT models.
>
> | Model | Input (\$/1M) | Output (\$/1M) | Cache read (\$/1M) | Service tiers | Docs |
> | - | - | - | - | - | - |
> | `openai/gpt-6.1-sol` | 2.00 (≤272k) 4.00 (>272k) | 10.00 (≤272k) 15.00 (>272k) | 95% off input | `flex`, `priority` | [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) |
> | `openai/gpt-6-astra` | 10.00 (≤272k) 20.00 (>272k) | 50.00 (≤272k) 75.00 (>272k) | 90% off input | `flex`, `priority` | [OpenAI models](https://developers.openai.com/api/docs/models) |
> | `openai/gpt-6-sol` | 2.00 (≤272k) 4.00 (>272k) | 10.00 (≤272k) 15.00 (>272k) | 90% off input | `flex`, `priority` | [OpenAI models](https://developers.openai.com/api/docs/models) |
> | `openai/gpt-6-luna` | 0.10 (≤272k) 0.20 (>272k) | 0.50 (≤272k) 0.75 (>272k) | 90% off input | `flex`, `priority` | [OpenAI models](https://developers.openai.com/api/docs/models) |
> | `openai/gpt-5.6-sol` | 4.00 (≤272k) 8.00 (>272k) | 20.00 (≤272k) 30.00 (>272k) | 90% off input | `flex`, `priority` | [GPT-5.6](https://openai.com/index/gpt-5-6/) |
> | `openai/gpt-5.6-terra` | 2.00 (≤272k) 4.00 (>272k) | 12.00 (≤272k) 18.00 (>272k) | 90% off input | `flex`, `priority` | [GPT-5.6](https://openai.com/index/gpt-5-6/) |
> | `openai/gpt-5.6-luna` | 0.20 (≤272k) 0.40 (>272k) | 1.20 (≤272k) 1.80 (>272k) | 90% off input | `flex`, `priority` | [GPT-5.6](https://openai.com/index/gpt-5-6/) |
> | `openai/gpt-5.5` | 5.00 (≤272k) 10.00 (>272k) | 30.00 (≤272k) 45.00 (>272k) | 90% off input | `flex`, `priority` | [GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5) |

> [tab] Google
>
> > [card] Google
> >
> > Gemini 4 Argon and Gemini 3.6, 3.7, and 3.8 Flash.
>
> | Model | Input (\$/1M) | Output (\$/1M) | Cache read (\$/1M) | Service tiers | Docs |
> | - | - | - | - | - | - |
> | `google/gemini-4-argon` | 2.00 | 10.00 | 0.10 | Default only | [Gemini 4 Argon](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon) |
> | `google/gemini-3.6-flash` | 1.50 | 7.50 | 0.15 | — | [Gemini 3.6 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash) |
> | `google/gemini-3.7-flash` | 0.75 | 3.75 | 0.075 | — | [Gemini 3.7 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash) |
> | `google/gemini-3.8-flash` | 0.75 | 3.75 | 0.075 | — | [Gemini models](https://ai.google.dev/gemini-api/docs/models) |
>
> Gemini 4 Argon rates are introductory pricing through November 30, 2026. Reasoning tokens are billed at the output-token rate.

> [tab] xAI
>
> > [card] xAI
> >
> > Grok 4.7, 4.6, and 4.5.
>
> | Model | Input (\$/1M) | Output (\$/1M) | Cache read (\$/1M) | Service tiers | Docs |
> | - | - | - | - | - | - |
> | `xai/grok-4.7` | 2.00 (\<200k) 4.00 (≥200k) | 6.00 (\<200k) 12.00 (≥200k) | 0.50 (\<200k) 1.00 (≥200k) | — | [Grok 4.7](https://docs.x.ai/developers/models/grok-4.7) |
> | `xai/grok-4.6` | 2.00 (\<200k) 4.00 (≥200k) | 6.00 (\<200k) 12.00 (≥200k) | 0.50 (\<200k) 1.00 (≥200k) | — | [Grok 4.6](https://docs.x.ai/developers/models/grok-4.6) |
> | `xai/grok-4.5` | 2.00 (\<200k) 4.00 (≥200k) | 6.00 (\<200k) 12.00 (≥200k) | 0.30 (\<200k) 0.60 (≥200k) | — | [Grok 4.5](https://docs.x.ai/developers/models) |

> [tab] Z.AI
>
> > [card] Z.AI
> >
> > GLM 5.3 and GLM 5.3 Flash — Z.AI reasoning models.
>
> | Model | Input (\$/1M) | Output (\$/1M) | Cache read (\$/1M) | Service tiers | Docs |
> | - | - | - | - | - | - |
> | `perplexity/glm-5.3` | 1.40 | 4.40 | 0.26 | — | [GLM](https://docs.z.ai) |
> | `perplexity/glm-5.3-flash` | 0.15 | 0.50 | 0.03 | — | [GLM-5.3 Flash](https://huggingface.co/zai-org/GLM-5.3-Flash) |

> [tab] DeepSeek
>
> > [card] DeepSeek
> >
> > DeepSeek V4 Pro, hosted by Perplexity.
>
> | Model | Input (\$/1M) | Output (\$/1M) | Cache read (\$/1M) | Service tiers | Docs |
> | - | - | - | - | - | - |
> | `perplexity/deepseek-v4-pro-0813` | 1.32 | 3.96 | 0.044 | — | — |

> [tab] Moonshot AI
>
> > [card] Moonshot AI
> >
> > Kimi K3 — Moonshot AI's flagship reasoning model.
>
> | Model | Input (\$/1M) | Output (\$/1M) | Cache read (\$/1M) | Service tiers | Docs |
> | - | - | - | - | - | - |
> | `perplexity/kimi-k3` | 3.00 | 15.00 | 0.30 | — | [Kimi K3](https://huggingface.co/moonshotai/Kimi-K3) |
>
> > [!NOTE]
> >
> > Kimi K3 accepts `minimal`, `low`, `medium`, `high`, `xhigh`, and `max` reasoning effort. `minimal` uses low effort, while `xhigh` and `max` use maximum effort. Reasoning tokens are billed at the output-token rate.

> [tab] NVIDIA
>
> > [card] NVIDIA
> >
> > Nemotron 3.5 Super is a reasoning model with a 1,048,576-token context window and up to 131,072 output tokens. It accepts text input only.
>
> | Model | Input (\$/1M) | Output (\$/1M) | Cache read (\$/1M) | Service tiers | Docs |
> | - | - | - | - | - | - |
> | `perplexity/nemotron-3.5-super-120b-a12b` | 0.20 | 0.50 | 0.04 | — | — |

> [tab] Perplexity
>
> > [card] Perplexity
> >
> > Perplexity's grounded search model.
>
> | Model | Input (\$/1M) | Output (\$/1M) | Cache read (\$/1M) | Service tiers | Docs |
> | - | - | - | - | - | - |
> | `perplexity/sonar` | 0.25 | 2.50 | 0.0625 | — | — |

## Service tiers

Omit `service_tier`, or set it to `auto` or `default`, to use default processing. `flex` uses lower-cost, best-effort capacity at 0.5× the listed token prices. `priority` uses higher-priority processing at 2× the listed token prices. `fast` is accepted as an alias for `priority`. These multipliers apply only to models that list the tier in the **Service tiers** column. Other models always bill at the listed rate.

When you provide `model` or `models`, the Agent API applies `flex` or `priority` only if the selected model—or every model in a fallback list—supports that tier. An unsupported tier does not cause the request to be rejected; the API ignores `service_tier` and uses default processing. Requests that specify only an effort level or profile retain the tier until the model is resolved. The response's `service_tier` field reports the tier that served the request.

> [!WARNING]
>
> Not all third-party models support all features (e.g., reasoning, tools). Check model documentation for specific capabilities.

## Using a Model

```python Python theme={null}
from perplexity import Perplexity

client = Perplexity()

response = client.responses.create(
    model="openai/gpt-5.6-sol",
    input="Explain the difference between supervised and unsupervised learning in machine learning.",
    max_output_tokens=300,
)

print(f"Response ID: {response.id}")
print(response.output_text)
```

```typescript Typescript theme={null}
import Perplexity from '@perplexity-ai/perplexity_ai';

const client = new Perplexity();

const response = await client.responses.create({
    model: "openai/gpt-5.6-sol",
    input: "Explain the difference between supervised and unsupervised learning in machine learning.",
    max_output_tokens: 300,
});

console.log(`Response ID: ${response.id}`);
console.log(response.output_text);
```

```bash cURL theme={null}
curl https://api.perplexity.ai/v1/agent \
  -H "Authorization: Bearer $PERPLEXITY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-5.6-sol",
    "input": "Explain the difference between supervised and unsupervised learning in machine learning.",
    "max_output_tokens": 300
  }' | jq
```

> [accordion] Response
>
> ```json theme={null}
> {
>   "id": "resp_85783af3-39c4-4565-9f09-144482151abf",
>   "created_at": 1779391438,
>   "model": "openai/gpt-5.6-sol",
>   "object": "response",
>   "output": [
>     {
>       "results": [
>         {
>           "id": 1,
>           "snippet": "Supervised learning is a machine learning technique that uses labeled data sets to train artificial intelligence (AI) models to identify the underlying patterns and relationships.\nThe goal of the...",
>           "title": "What Is Supervised Learning? | IBM",
>           "url": "https://www.ibm.com/think/topics/supervised-learning",
>           "date": "2025-09-12",
>           "last_updated": "2026-03-31",
>           "source": "web"
>         },
>         {
>           "id": 2,
>           "snippet": "Unsupervised learning, also known as unsupervised machine learning, uses machine learning (ML) algorithms to analyze and cluster unlabeled data sets.\nThese algorithms discover hidden patterns or data...",
>           "title": "What Is Unsupervised Learning? - IBM",
>           "url": "https://www.ibm.com/think/topics/unsupervised-learning",
>           "date": "2021-09-23",
>           "last_updated": "2026-03-31",
>           "source": "web"
>         },
>         {
>           "id": 3,
>           "snippet": "The difference between supervised and unsupervised **learning lies in how they use data and their goals**.\n**Supervised learning** relies on **labeled datasets, where each input is paired with a...",
>           "title": "Difference between Supervised and Unsupervised Learning",
>           "url": "https://www.geeksforgeeks.org/machine-learning/difference-between-supervised-and-unsupervised-learning/",
>           "date": "2025-07-11",
>           "last_updated": "2026-05-19",
>           "source": "web"
>         },
>         {
>           "id": 4,
>           "snippet": "Supervised learning is a type of machine learning where a model learns from labelled data, meaning each input has a correct output.\nThe model compares its predictions with actual results and improves...",
>           "title": "Supervised Machine Learning - GeeksforGeeks",
>           "url": "https://www.geeksforgeeks.org/machine-learning/supervised-machine-learning/",
>           "date": "2026-05-09",
>           "last_updated": "2026-05-19",
>           "source": "web"
>         },
>         {
>           "id": 5,
>           "snippet": "Unsupervised Learning is a type of machine learning where the model works without labelled data.\nIt learns patterns on its own by grouping similar data points or finding hidden structures without any...",
>           "title": "Unsupervised Machine Learning - GeeksforGeeks",
>           "url": "https://www.geeksforgeeks.org/machine-learning/unsupervised-learning/",
>           "date": "2026-04-30",
>           "last_updated": "2026-05-19",
>           "source": "web"
>         },
>         {
>           "id": 6,
>           "snippet": "The biggest difference between supervised and unsupervised machine learning is the type of data used.\nSupervised learning uses labeled training data, and unsupervised learning does not.\nMore simply...",
>           "title": "Supervised vs. unsupervised learning - Google Cloud",
>           "url": "https://cloud.google.com/discover/supervised-vs-unsupervised-learning",
>           "date": null,
>           "last_updated": "2026-05-18",
>           "source": "web"
>         },
>         {
>           "id": 7,
>           "snippet": "Supervised learning is a category of machine learning that uses labeled datasets to train algorithms to predict outcomes and recognize patterns.\nUnlike unsupervised learning, supervised learning...",
>           "title": "What is Supervised Learning? | Google Cloud",
>           "url": "https://cloud.google.com/discover/what-is-supervised-learning",
>           "date": "2025-04-12",
>           "last_updated": "2026-05-18",
>           "source": "web"
>         },
>         {
>           "id": 8,
>           "snippet": "Unsupervised learning in artificial intelligence is a type of machine learning that learns from data without human supervision.\nUnlike supervised learning, unsupervised machine learning models are...",
>           "title": "What is unsupervised learning? - Google Cloud",
>           "url": "https://cloud.google.com/discover/what-is-unsupervised-learning",
>           "date": null,
>           "last_updated": "2026-05-19",
>           "source": "web"
>         },
>         {
>           "id": 9,
>           "snippet": "- Supervised vs. unsupervised learning serve different purposes: supervised learning uses labeled data to make precise predictions and classifications, while unsupervised learning finds hidden...",
>           "title": "Supervised vs Unsupervised Learning - Databricks",
>           "url": "https://www.databricks.com/blog/supervised-vs-unsupervised-learning",
>           "date": "2026-02-17",
>           "last_updated": "2026-05-20",
>           "source": "web"
>         },
>         {
>           "id": 10,
>           "snippet": "Supervised learning algorithms train on sample data that specifies both the algorithm's input and output.\nFor example, the data could be images of handwritten numbers that are annotated to indicate...",
>           "title": "Supervised vs Unsupervised Learning - Difference Between ... - AWS",
>           "url": "https://aws.amazon.com/compare/the-difference-between-machine-learning-supervised-and-unsupervised/",
>           "date": "2026-05-13",
>           "last_updated": "2026-05-20",
>           "source": "web"
>         },
>         {
>           "id": 11,
>           "snippet": "In a supervised learning model, the algorithm learns on a labeled dataset, providing an answer key that the algorithm can use to evaluate its accuracy on training data.\n...\nIf you’re learning a task...",
>           "title": "NVIDIA Blog: Supervised Vs. Unsupervised Learning",
>           "url": "https://blogs.nvidia.com/blog/supervised-unsupervised-learning/",
>           "date": "2018-08-02",
>           "last_updated": "2026-04-13",
>           "source": "web"
>         },
>         {
>           "id": 12,
>           "snippet": "**Supervised Learning** is a machine learning approach where models are trained on labeled data—input examples paired with correct output answers.\nThe algorithm learns to map inputs to outputs by...",
>           "title": "What is Supervised Learning? - Stanford HAI",
>           "url": "https://hai.stanford.edu/ai-definitions/what-is-supervised-learning",
>           "date": "2024-09-10",
>           "last_updated": "2026-05-06",
>           "source": "web"
>         },
>         {
>           "id": 13,
>           "snippet": "**Unsupervised learning** is a framework in machine learning where, in contrast to supervised learning, algorithms learn patterns exclusively from unlabeled data.",
>           "title": "Unsupervised learning - Wikipedia",
>           "url": "https://en.wikipedia.org/wiki/Unsupervised_learning",
>           "date": "2003-05-25",
>           "last_updated": "2026-03-31",
>           "source": "web"
>         },
>         {
>           "id": 14,
>           "snippet": "The difference between supervised and unsupervised learning is simple: it's about how much human guidance you give the machine learning algorithm.\n...\nIn supervised learning, humans provide more...",
>           "title": "Supervised vs. Unsupervised Learning: The Basics Explained | TDWI",
>           "url": "https://tdwi.org/blogs/ai-101/2025/09/supervised-vs-unsupervised-learning.aspx",
>           "date": "2025-09-20",
>           "last_updated": "2026-05-21",
>           "source": "web"
>         }
>       ],
>       "type": "search_results",
>       "queries": [
>         "supervised learning definition",
>         "unsupervised learning definition",
>         "difference between supervised and unsupervised learning"
>       ]
>     },
>     {
>       "id": "msg_edef631a-cd00-4ba7-85ab-cea139ca9f13",
>       "content": [
>         {
>           "text": "Supervised learning learns from **labeled** examples to predict known outcomes, while unsupervised learning finds structure in **unlabeled** data without predefined outputs.[web:1][web:2][web:6][web:8]\n\n## Core idea\n\n- Supervised learning uses datasets where each input (features) comes with a correct output label, and the model learns a mapping from inputs to outputs to make predictions on new data.[web:1][web:7][web:12]  \n- Unsupervised learning uses datasets that have inputs only, with no labels, and algorithms try to discover patterns such as clusters, groups, or anomalies in the data.[web:2][web:5][web:8][web:13]\n\n## Data and “answers”\n\n- In supervised learning, training data is “labeled,” meaning each example is paired with the right answer (for example, an email plus a tag “spam” or “not spam”).[web:1][web:4][web:7][web:10][web:12]  \n- In unsupervised learning, the data is “unlabeled”; the model receives raw examples and must organize them or detect structure without being told the correct answer for each case.[web:2][web:5][web:8][web:13]\n\n## Typical goals\n\n- Supervised learning aims at prediction: classification (discrete labels like spam/not spam) and regression (continuous values like house prices), with a clear, predefined target variable.[web:1][web:3][web:9]  \n- Unsupervised learning aims at pattern discovery: clustering similar items, finding hidden groupings, dimensionality reduction, or detecting outliers without a predefined target.[web:2][web:3][web:5][web:8][web:9]\n\n## Examples of each\n\n- Common supervised methods and tasks include logistic regression for spam detection, decision trees for credit approval, and image classifiers trained on labeled pictures of objects.[web:1][web:4][web:7][web:9][web:10]  \n- Common unsupervised methods and tasks include k-means clustering for grouping customers by behavior, anomaly detection in network traffic, and algorithms like PCA for compressing or visualizing high-dimensional data.[web:2][web:3][web:5][web:8][web:9]\n\n## Practical trade‑offs\n\n- Supervised learning typically delivers more accurate, measurable predictions but requires substantial human effort to create labeled datasets and a clear definition of the prediction goal.[web:2][web:6][web:7][web:9][web:14]  \n- Unsupervised learning requires less upfront labeling work and is well suited for exploration and discovering unknown structure, but its results are often harder to evaluate because there is no single “correct” answer.[web:2][web:3][web:8][web:9][web:14]",
>           "type": "output_text",
>           "annotations": [],
>           "logprobs": []
>         }
>       ],
>       "role": "assistant",
>       "status": "completed",
>       "type": "message"
>     }
>   ],
>   "status": "completed",
>   "error": null,
>   "usage": {
>     "input_tokens": 6599,
>     "output_tokens": 657,
>     "total_tokens": 7256,
>     "cost": {
>       "currency": "USD",
>       "input_cost": 0.01206,
>       "output_cost": 0.01314,
>       "total_cost": 0.02913,
>       "cache_creation_cost": null,
>       "cache_read_cost": 0.00143,
>       "tool_calls_cost": 0.0025
>     },
>     "input_tokens_details": {
>       "cache_creation_input_tokens": 0,
>       "cache_read_input_tokens": 3584,
>       "cached_tokens": 3584
>     },
>     "tool_calls_details": {
>       "search_web": {
>         "invocation": 1
>       }
>     },
>     "output_tokens_details": {
>       "reasoning_tokens": 0
>     }
>   },
>   "completed_at": 1779391438
> }
> ```

> [!TIP]
>
> **See Your Costs in Real-Time:** Every response includes a `usage` field with exact input tokens, output tokens, and cache read tokens. Calculate your cost instantly using the pricing table above.
>
> ```json theme={null}
> {
>   "usage": {
>     "input_tokens": 150,
>     "output_tokens": 320,
>     "total_tokens": 470
>   }
> }
> ```

## Model Fallback

For high-availability applications, you can specify multiple models in a fallback chain. When one model fails or is unavailable, the API automatically tries the next model in the chain.

> [card] [Model Fallback Chain](https://docs.perplexity.ai/docs/agent-api/model-fallback.md)
>
> Learn how to use model fallback chains to ensure high availability and reliability by automatically trying multiple models when one fails.

> [!NOTE]
>
> **Example:**
>
> ```python theme={null}
> response = client.responses.create(
>     models=["openai/gpt-5.6-sol", "anthropic/claude-sonnet-5-5", "google/gemini-3.8-flash"],
>     input="Your question here",
>     max_output_tokens=8192,
> )
> ```
>
> For detailed examples, pricing information, and best practices, see the [Model Fallback documentation](https://docs.perplexity.ai/docs/agent-api/model-fallback.md).

## Next Steps

> [card] [Web Search](https://docs.perplexity.ai/docs/agent-api/tools/web-search.md)
>
> Equip your model with web search for source-grounded context.

> [card] [Prompt Guide](https://docs.perplexity.ai/docs/agent-api/prompt-guide.md)
>
> Write prompts that get the most out of the Agent API.

> [card] [Output Control](https://docs.perplexity.ai/docs/agent-api/output-control.md)
>
> Shape responses with structured outputs and JSON schemas.

> [card] [Finance Search](https://docs.perplexity.ai/docs/agent-api/tools/finance-search.md)
>
> Query market data, filings, and ticker-level information.
