> ## Documentation Index
> Fetch the complete documentation index at: https://inference-docs.cerebras.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Qwen 3.8 27B

> Alibaba's 27B dense multimodal model for agentic coding, tool use, research, and long-running workflows. It accepts text and image inputs and supports configurable reasoning.

Model ID: `qwen-3.8-27b`. Context window: 64K tokens (65,536) for Free Trial and 128K tokens (131,072) for paid tiers and trial customers. Maximum output: 32K tokens (32,768) for Free Trial and 40K tokens (40,960) for paid tiers and trial customers. Pricing: $0.99 per million input tokens and $1.49 per million output tokens. Free Trial rate limits: 5 requests per minute, 30K uncached tokens per minute, 90K total tokens per minute, and 1M tokens per day. Developer rate limits: 300 requests per minute, 150K uncached tokens per minute, 750K total tokens per minute (temporarily increased from 450K), and no daily token limit. Modality: multimodal. Accepts text and base64-encoded PNG or JPEG image inputs and produces text output. Maximum images per request: 2 for Free Trial, 10 for Developer and Enterprise accounts using Shared Inference. Maximum request payload: 10 MiB. Capabilities: Image Inputs, Reasoning, Streaming, Sampling Controls, Structured Outputs, Tool Calling, Parallel Tool Calling, and Prompt Caching. Reasoning defaults to `high`. Set `reasoning_effort` to `none` to disable it. `clear_thinking` defaults to `false`, which preserves prior assistant reasoning supplied in conversation history. The `hidden` reasoning format is not supported. See the [Structured Outputs guide](https://inference-docs.cerebras.ai/capabilities/structured-outputs.md) for strict schema support and limitations.

> [!NOTE]
>
> Qwen 3.8 27B is available through both Shared Inference and [Dedicated Inference](https://inference-docs.cerebras.ai/dedicated/overview.md#supported-models). Use `qwen-3.8-27b` with Shared Inference or your assigned endpoint ID with Dedicated Inference.

Model ID

`qwen-3.8-27b`

[Try in Playground](https://cloud.cerebras.ai)
[Model card](https://huggingface.co/Qwen/Qwen3.8-27B)

### Model Stats

SPEED

CONTEXT WINDOW

Free
64k tokens

Paid
128k tokens

MAX OUTPUT

Free
32k tokens

Paid
40k tokens

MODALITY

Input

Output

### Pricing

per million tokens

Input

\$0.99

Output

\$1.49

Developer pricing. For volume discounts and enterprise features, see our
[pricing page](https://www.cerebras.ai/pricing)
.

### Need Higher Limits?

Reach out for custom pricing with our Enterprise tier for higher rate limits and dedicated support.

[Contact Sales](https://cerebras.ai/contact-us)
