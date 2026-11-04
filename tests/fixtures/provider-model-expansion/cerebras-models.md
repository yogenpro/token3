> ## Documentation Index
> Fetch the complete documentation index at: https://inference-docs.cerebras.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Model Catalog

> Browse all models available with Cerebras Shared Inference.

You can use models available with Cerebras Shared Inference on the Free Trial and Pay as You Go tiers, subject to [rate limits](https://inference-docs.cerebras.ai/support/rate-limits.md) and [pricing](https://inference-docs.cerebras.ai/support/pricing.md). For additional model families, reserved capacity, higher throughput, and production SLAs, see [Dedicated Inference](https://inference-docs.cerebras.ai/dedicated/overview.md).

> [!TIP]
>
> New here? Follow the [Quickstart](https://inference-docs.cerebras.ai/quickstart.md) to make your first API call. To pick a model by use case, see the [model selection guide](https://inference-docs.cerebras.ai/models/choose-a-model.md). Select any model name below for full specs, capabilities, and per-tier limits.

## Available Models

| Model Name | Model ID | Parameters | Context (free / paid) | Speed (tokens/s) |
| :- | :- | :- | :- | :- |
| [OpenAI GPT OSS](https://inference-docs.cerebras.ai/models/openai-oss.md) | `gpt-oss-120b` | 120 billion | 65k / 131k | \~3000 |
| [Qwen 3.8 27B](https://inference-docs.cerebras.ai/models/qwen-3.8-27b.md) | `qwen-3.8-27b` | 27 billion | 64k / 128k | \~1850 |

> [!TIP]
>
> Looking for more models? Many additional model families are available through [Dedicated Inference](https://inference-docs.cerebras.ai/dedicated/overview.md#supported-models).

## Model Compression

This section provides transparency about the compression state of each model available on our platform.

We host a variety of open-source models from the community. We do not currently host pruned models with Shared Inference. All models served through Shared Inference are the original, unpruned versions.

We research pruning techniques like REAP (Router-weighted Expert Activation Pruning) and share these pruned models with the research community on Hugging Face. These pruned models are not available through Shared Inference. You can read more about REAP in our [research blog](https://www.cerebras.ai/blog/reap). **All Shared Inference models are unpruned.**

Cerebras uses selective weight-only quantization only during storage to preserve maximal quality. This means that the weights are stored in partial 16-bit / 8-bit / 4-bit, in-line with industry standards. For quality, sensitive layers are stored at full precision with dequantization on the fly, so operations are done in high precision. The activations, attention, and kv cache remain in full precision and unquantized.

### Frequently Asked Questions

> [accordion] Will you change a model's architecture without notice?
>
> No. We are committed to serving the original weights for existing model IDs without modification. We do not alter model architectures via pruning on our hosted portfolio. If we explore additional compression techniques like pruning in the future, we will offer them as separate model variants with distinct model IDs. This keeps the difference transparent and lets you choose the variant that best fits your needs.

> [accordion] Where can I find your REAP pruned models?
>
> Our REAP pruned models are available on Hugging Face for research and experimentation purposes: [Cerebras REAP Collection](https://huggingface.co/collections/cerebras/cerebras-reap). These models demonstrate our pruning research but are not served through our production API.

> [accordion] What are compression, quantization, and pruning?
>
> **Compression** is an umbrella term for techniques that reduce model size or computational requirements. Common compression techniques include:
>
> * **Quantization**: Reducing the precision of numbers used to represent model weights (e.g., converting from FP16 to FP8). This reduces memory usage without changing the model's architecture.
> * **Pruning**: Permanently removing parts of a model, like layers or experts, to reduce model size. This changes the model's architecture and creates a different model.
