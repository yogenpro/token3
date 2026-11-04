> ## Documentation Index
> Fetch the complete documentation index at: https://inference-docs.cerebras.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# OpenAI GPT OSS

> This model excels at efficient reasoning across science, math, and coding applications. It's ideal for real-time coding assistance, processing large documents for Q&A and summarization, agentic research workflows, and regulated on-premises workloads.

Model ID: `gpt-oss-120b`. Pricing: $0.35 per million input tokens, $0.75 per million output tokens. Context window: 65k tokens (free tier), 131k tokens (paid). Max output: 32k tokens (free tier), 40k tokens (paid). Speed: \~3000 tokens/sec. Capabilities: Reasoning, Streaming, Structured Outputs, Tool Calling, Prompt Caching. Free tier rate limits: 30 requests/min, 60k input tokens/min, 1M tokens/day. Notes: Use the `reasoning_effort` parameter to control reasoning; the default effort level is `medium`. When `min_tokens` is set, the model may generate EOS tokens which can cause parser failures. This model may call tools that aren't directly specified — reprompt with "you're hallucinating a tool call" to help it self-correct. The API maps the "system" role to developer-level instructions in the prompt hierarchy.

Model ID

`gpt-oss-120b`

[Try in Playground](https://cloud.cerebras.ai)
[Model card](https://openai.com/index/gpt-oss-model-card/)

### Model Stats

SPEED

CONTEXT WINDOW

Free
65k tokens

Paid
131k tokens

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

\$0.35

Output

\$0.75

Developer pricing. For volume discounts and enterprise features, see our
[pricing page](https://www.cerebras.ai/pricing)
.

### Need Higher Limits?

Reach out for custom pricing with our Enterprise tier for higher rate limits and dedicated support.

[Contact Sales](https://cerebras.ai/contact-us)
