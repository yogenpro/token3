> ## Documentation Index
> Fetch the complete documentation index at: https://inference-docs.cerebras.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Public models

Retrieve details about publicly available Cerebras models without an API key, including context length, pricing, and supported features. This endpoint supports multiple response formats for compatibility with different platforms.

> [!NOTE]
>
> This endpoint is **public** and does not require an API key.

## Supported Formats

The endpoint supports three response formats via the `format` query parameter:

* **Default (Cerebras)** - Native Cerebras format
* **OpenRouter** - OpenRouter-compatible format
* **HuggingFace** - HuggingFace-compatible format

## Query Parameters

**format** `string`

Response format. Options: `openrouter`, `huggingface`. Omit for default Cerebras format.

## Response

### Default Format

**object** `string`

The object type, which is always `list` for list responses or `model` for single model responses.

**data** `array`

Array of model objects (only in list responses).

**model properties**

**id** `string`

The model identifier (e.g., `gpt-oss-120b`).

**object** `string`

The object type, which is always `model`.

**created** `integer`

The Unix timestamp (in seconds) of when the model was created.

**owned\_by** `string`

The organization that owns the model.

**name** `string`

Human-readable model name.

**description** `string`

Description of the model's capabilities and recommended use cases.

**hugging\_face\_id** `string`

The HuggingFace repository identifier for this model.

**pricing** `object`

Pricing per token in USD.

**pricing fields**

**prompt** `string`

Cost per prompt token.

**completion** `string`

Cost per completion token.

**capabilities** `object`

Boolean flags for supported features.

**capability fields**

**streaming** `boolean`

Whether streaming is supported.

**function\_calling** `boolean`

Whether function calling is supported.

**structured\_outputs** `boolean`

Whether structured outputs are supported.

**vision** `boolean`

Whether vision/image input is supported.

**json\_mode** `boolean`

Whether JSON mode is supported.

**tools** `boolean`

Whether tool use is supported.

**tool\_choice** `boolean`

Whether tool choice is supported.

**parallel\_tool\_calls** `boolean`

Whether parallel tool calls are supported.

**response\_format** `boolean`

Whether response format control is supported.

**reasoning** `boolean`

Whether the model supports reasoning.

**supported\_parameters** `object`

Boolean flags for supported API parameters.

**architecture** `object`

Model architecture details.

**architecture fields**

**modality** `string`

Input/output modality (e.g., `text`).

**tokenizer** `string`

Tokenizer type.

**instruct\_type** `string`

Instruction tuning format.

**limits** `object`

Model limits.

**limit fields**

**max\_context\_length** `integer`

Maximum context window in tokens.

**max\_completion\_tokens** `integer`

Maximum completion tokens.

**requests\_per\_minute** `integer`

Requests per minute limit (null if unlimited).

**tokens\_per\_minute** `integer`

Tokens per minute limit (null if unlimited).

**deprecated** `boolean`

Whether this model is deprecated.

**preview** `boolean`

Whether this model is in preview.

**quantization** `string`

Quantization method used for the model.

### OpenRouter Format

**data** `array`

Array of model objects with extended metadata.

**extended properties**

**id** `string`

The model identifier.

**hugging\_face\_id** `string`

The HuggingFace repository identifier.

**name** `string`

Human-readable model name.

**input\_modalities** `array`

Supported input types (e.g., `["text"]`).

**output\_modalities** `array`

Supported output types (e.g., `["text"]`).

**context\_length** `integer`

Maximum context window size in tokens.

**max\_output\_length** `integer`

Maximum output length in tokens.

**pricing** `object`

Pricing information per token.

**pricing fields**

**prompt** `string`

Cost per prompt token.

**completion** `string`

Cost per completion token.

**request** `string`

Cost per request (typically `"0"`).

**image** `string`

Cost per image token (typically `"0"` for text-only models).

**input\_cache\_read** `string`

Cost per cached input token read (typically `"0"`).

**input\_cache\_write** `string`

Cost per cached input token write (typically `"0"`).

**supported\_sampling\_parameters** `array`

List of supported sampling parameters.

**supported\_features** `array`

List of supported features (e.g., `["tools", "json_mode", "structured_outputs"]`).

### HuggingFace Format

**data** `array`

Array of model objects.

**properties**

**id** `string`

The model identifier.

**hugging\_face\_id** `string`

The HuggingFace repository identifier.

**object** `string`

The object type, which is always `model`.

**created** `integer`

The Unix timestamp (in seconds) of when the model was created.

**owned\_by** `string`

The organization that owns the model.

**pricing** `object`

Pricing in USD per million tokens.

**pricing fields**

**input** `number`

Price per million input tokens.

**output** `number`

Price per million output tokens.

**context\_length** `integer`

Maximum context window size in tokens.

**capabilities** `object`

Boolean flags for supported features.

```bash cURL (Default) theme={null}
curl -sS 'https://api.cerebras.ai/public/v1/models' | jq
```

```bash cURL (OpenRouter) theme={null}
curl -sS 'https://api.cerebras.ai/public/v1/models?format=openrouter' | jq
```

```bash cURL (HuggingFace) theme={null}
curl -sS 'https://api.cerebras.ai/public/v1/models?format=huggingface' | jq
```

```python Python theme={null}
import httpx

# Default format
response = httpx.get("https://api.cerebras.ai/public/v1/models")
models = response.json()

# OpenRouter format
response = httpx.get(
    "https://api.cerebras.ai/public/v1/models",
    params={"format": "openrouter"}
)
models = response.json()

# HuggingFace format
response = httpx.get(
    "https://api.cerebras.ai/public/v1/models",
    params={"format": "huggingface"}
)
models = response.json()
```

```javascript JavaScript theme={null}
// Default format
const response = await fetch('https://api.cerebras.ai/public/v1/models');
const models = await response.json();

// OpenRouter format
const response = await fetch(
  'https://api.cerebras.ai/public/v1/models?format=openrouter'
);
const models = await response.json();

// HuggingFace format
const response = await fetch(
  'https://api.cerebras.ai/public/v1/models?format=huggingface'
);
const models = await response.json();
```

```json Default Format theme={null}
{
  "object": "list",
  "data": [
    {
      "id": "gpt-oss-120b",
      "object": "model",
      "created": 1754438400,
      "owned_by": "OpenAI",
      "name": "OpenAI GPT OSS",
      "description": "This model excels at efficient reasoning across science, math, and coding applications. It's ideal for real-time coding assistance, processing large documents for Q&A and summarization, agentic research workflows, and regulated on-premises workloads.",
      "hugging_face_id": "openai/gpt-oss-120b",
      "pricing": {
        "prompt": "0.00000035",
        "completion": "0.00000075"
      },
      "capabilities": {
        "streaming": true,
        "function_calling": true,
        "structured_outputs": true,
        "vision": false,
        "json_mode": true,
        "tools": true,
        "tool_choice": true,
        "parallel_tool_calls": false,
        "response_format": true,
        "reasoning": true
      },
      "supported_parameters": {
        "temperature": true,
        "top_p": true,
        "seed": true,
        "stop": true,
        "max_completion_tokens": true,
        "logprobs": true,
        "top_logprobs": true,
        "frequency_penalty": true,
        "presence_penalty": true,
        "logit_bias": true,
        "repetition_penalty": false
      },
      "architecture": {
        "modality": "text",
        "tokenizer": "GPT",
        "instruct_type": "harmony"
      },
      "limits": {
        "max_context_length": 131072,
        "max_completion_tokens": 40960,
        "requests_per_minute": null,
        "tokens_per_minute": null
      },
      "datacenter_locations": [],
      "deprecated": false,
      "preview": false,
      "quantization": "FP16/8 (weights only)"
    }
  ]
}
```

```json OpenRouter Format theme={null}
{
  "data": [
    {
      "id": "gpt-oss-120b",
      "hugging_face_id": "openai/gpt-oss-120b",
      "name": "OpenAI GPT OSS",
      "created": 1754438400,
      "input_modalities": ["text"],
      "output_modalities": ["text"],
      "quantization": "fp16",
      "context_length": 131072,
      "max_output_length": 40960,
      "pricing": {
        "prompt": "0.00000035",
        "completion": "0.00000075",
        "request": "0",
        "image": "0",
        "input_cache_read": "0",
        "input_cache_write": "0"
      },
      "supported_sampling_parameters": [
        "temperature",
        "top_p",
        "stop",
        "seed",
        "frequency_penalty",
        "presence_penalty",
        "max_tokens",
        "logprobs",
        "top_logprobs",
        "logit_bias"
      ],
      "supported_features": [
        "tools",
        "json_mode",
        "structured_outputs",
        "reasoning"
      ]
    }
  ]
}
```

```json HuggingFace Format theme={null}
{
  "data": [
    {
      "id": "gpt-oss-120b",
      "hugging_face_id": "openai/gpt-oss-120b",
      "object": "model",
      "created": 1754438400,
      "owned_by": "OpenAI",
      "context_length": 131072,
      "pricing": {
        "input": 0.35,
        "output": 0.75
      },
      "capabilities": {
        "streaming": true,
        "function_calling": true,
        "structured_outputs": true,
        "vision": false
      }
    }
  ]
}
```

## Retrieve Specific Model

You can also retrieve information about a specific model by appending the model ID to the endpoint:

```
GET https://api.cerebras.ai/public/v1/models/{model_id}
```

### Path Parameters

**model\_id** `string` *required*

The ID of the model to retrieve (for example, `gpt-oss-120b` or `qwen-3.8-27b`).

```bash cURL theme={null}
curl -sS 'https://api.cerebras.ai/public/v1/models/gpt-oss-120b' | jq
```

```python Python theme={null}
import httpx

model_id = "gpt-oss-120b"
response = httpx.get(f"https://api.cerebras.ai/public/v1/models/{model_id}")
model = response.json()
```

```javascript JavaScript theme={null}
const modelId = 'gpt-oss-120b';
const response = await fetch(
  `https://api.cerebras.ai/public/v1/models/${modelId}`
);
const model = await response.json();
```

```json Response theme={null}
{
  "id": "gpt-oss-120b",
  "object": "model",
  "created": 1754438400,
  "owned_by": "OpenAI",
  "name": "OpenAI GPT OSS",
  "description": "This model excels at efficient reasoning across science, math, and coding applications. It's ideal for real-time coding assistance, processing large documents for Q&A and summarization, agentic research workflows, and regulated on-premises workloads.",
  "hugging_face_id": "openai/gpt-oss-120b",
  "pricing": {
    "prompt": "0.00000035",
    "completion": "0.00000075"
  },
  "capabilities": {
    "streaming": true,
    "function_calling": true,
    "structured_outputs": true,
    "vision": false,
    "json_mode": true,
    "tools": true,
    "tool_choice": true,
    "parallel_tool_calls": false,
    "response_format": true,
    "reasoning": true
  },
  "limits": {
    "max_context_length": 131072,
    "max_completion_tokens": 40960,
    "requests_per_minute": null,
    "tokens_per_minute": null
  },
  "deprecated": false,
  "preview": false,
  "quantization": "FP16/8 (weights only)"
}
```

## Use Cases

**Platform Integration** - Use the OpenRouter or HuggingFace formats to integrate Cerebras models into existing platforms that support these standards.

**Model Discovery** - Programmatically discover available models and their capabilities without authentication.

**Pricing Comparison** - Compare pricing across different models using the structured pricing information.

**Feature Detection** - Check which features (streaming, tools, JSON mode) are supported by each model.
