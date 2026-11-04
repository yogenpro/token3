> ## Documentation Index
> Fetch the complete documentation index at: https://platform.stepfun.ai/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Pricing and Rate Limits

## Pricing Details

### Pricing for Multimodal Reasoning Models

| Model | Billing unit | Input (cache miss) | Input (cache hit) | Output |
| :- | :- | :- | :- | :- |
| `step-5-preview` | 1M tokens | \$1.00 | \$0.10 | \$2.70 |
| `step-3.7-flash` | 1M tokens | \$0.20 | \$0.04 | \$1.15 |

For `step-5-preview`, the cache-miss input price includes writing new content to the cache. Output tokens include both the model's reasoning process and final answer. See [Prompt caching](https://platform.stepfun.ai/docs/en/guides/developer/prompt-cache.md) for details.

### Pricing for Reasoning Models

| Model | Billing unit | Input (cache miss) | Input (cache hit) | Output |
| :- | :- | :- | :- | :- |
| `step-3.5-flash` | 1M tokens | \$0.10 | \$0.02 | \$0.30 |
| `step-3.5-flash-2603` | 1M tokens | \$0.10 | \$0.02 | \$0.30 |

### Pricing for Vision Models

| Model | Billing unit | Input (cache miss) | Input (cache hit) | Output |
| :- | :- | :- | :- | :- |
| `step-1o-turbo-vision` | 1M tokens | \$0.36 | \$0.07 | \$1.15 |

Image input is counted and billed as tokens, just like text input. By default, each image uses 169 input tokens; with `detail` enabled, the token count is calculated from the image size.

### Pricing for Speech Models

**\[Pricing Notice]: StepAudio 3 series models are free for a limited time until 23:59:59 on November 8, 2026 (UTC+8), and will be billed at the prices listed below starting 00:00:00 on November 9, 2026 (UTC+8). In addition, due to rising compute costs, we have adjusted the pricing of certain voice models to continue ensuring service stability and inference quality. The new prices also take effect at 00:00:00 on November 9, 2026 (UTC+8); usage before then is billed at the previous rates. Charges are billed in US dollars (USD).**

### StepAudio 3 Series

| Model ID | Capability | Unit price | Notes |
| - | - | - | - |
| `stepaudio-3-realtime` | Realtime speech | \$0.125 / session minute (\$7.50 / session hour) | Billed by session duration. Both user speaking time and agent speaking time are counted. The minimum billing unit is one minute. Any partial minute is billed as a full minute; N minutes plus a partial minute is billed as N+1 minutes. |
| `stepaudio-3-tts` | Text-to-speech | \$14.00 / 1M billable input text characters | Billed by billable characters of the input text. One English letter counts as 1 character, one Japanese character counts as 2.5 characters, one Chinese character counts as 3 characters, and other characters (including digits, punctuation, and spaces) count as 1 character each. |
| `stepaudio-3-tts` | Voice cloning | \$1.50 / voice | Creates a custom voice from reference audio. Charged when the voice is added to the voice library; trial calls are charged only for synthesis. When a cloned or designed voice is used for speech synthesis, synthesis is charged separately at the text-to-speech unit price of the model used. |
| `stepaudio-3-tts` | Voice design | \$1.50 / voice | Creates a new voice from a text description. Charged when the voice is added to the voice library; trial calls are charged only for synthesis. When a cloned or designed voice is used for speech synthesis, synthesis is charged separately at the text-to-speech unit price of the model used. |
| `stepaudio-3-gen` | Audio generation | \$14.00 / 1M billable input text characters | Same as `stepaudio-3-tts`, billed by billable characters of the input text. One English letter counts as 1 character, one Japanese character counts as 2.5 characters, one Chinese character counts as 3 characters, and other characters (including digits, punctuation, and spaces) count as 1 character each. |
| `stepaudio-3-music` | Music generation · Tier 1 (no audio input): Song Creation, Instrumental | \$2.40 / output audio hour | Billed by the duration of the generated audio, in two tiers depending on whether audio input is provided. The minimum billing unit is one second, rounded to the nearest whole second. |
| `stepaudio-3-music` | Music generation · Tier 2 (with audio input): Song Adaptation, Vocal Accompaniment | \$4.80 / output audio hour | Billed by the duration of the generated audio, in two tiers depending on whether audio input is provided. The minimum billing unit is one second, rounded to the nearest whole second. |
| `stepaudio-3-asr-max` | Speech recognition | \$0.60 / audio hour | Billed by the duration of the input audio. |

### Other Models

### Realtime Voice & Voice Chat (Billed by Token)

Unit: USD / 1M tokens.

| Model ID | Input Price (Cache Miss) | Input Price (Cache Hit) | Output Price | Status |
| - | - | - | - | - |
| `stepaudio-2.5-realtime` | \$1.50 | \$0.30 | \$10.00 | Usage-based |
| `stepaudio-2.5-chat` | \$1.50 | \$0.30 | \$3.50 | Usage-based |
| `step-1o-audio` | \$3.57 | \$0.71 | \$8.57 | Usage-based |
| `step-audio-2` | \$1.43 | \$0.29 | \$10.00 | Usage-based |
| `step-audio-r1.5` | \$1.43 | \$0.29 | \$15.00 | Usage-based |

### Text-to-Speech

| Model ID | Unit price |
| - | - |
| `stepaudio-2.5-tts` | \$85.00 / 1M characters |
| `step-tts-2` | \$40.00 / 1M characters |
| `step-tts-mini` | \$13.00 / 1M characters |

> [!NOTE]
>
> `stepaudio-2.5-tts`, `step-tts-2`, `step-tts-mini`: one Chinese character counts as one character, two English letters count as one character, and two punctuation marks count as one character.

### Voice Cloning & Voice Design

| Model ID | Capability | Unit price |
| - | - | - |
| `stepaudio-2.5-tts`, `step-tts-2`, `step-tts-mini` | Voice cloning | \$1.50 / voice; charged when the voice is added to the voice library, and trial calls are charged only for synthesis |

> [!NOTE]
>
> Voice cloning: creates a custom voice from reference audio. Charged when the voice is added to the voice library; trial calls are charged only for synthesis.
>
> When a cloned or designed voice is used for speech synthesis, synthesis is charged separately at the text-to-speech unit price of the model used.

### Speech Recognition

| Model ID | Unit price |
| - | - |
| `stepaudio-2.5-asr` | \$0.05 / hour |
| `stepaudio-2.5-asr-stream` | \$0.40 / hour |
| `stepaudio-2-asr-pro` | \$0.29 / hour |
| `step-asr` | \$0.13 / hour |
| `step-asr-1.1` | \$0.31 / hour |
| `step-asr-1.1-stream` | \$0.81 / hour |

### Pricing for Image Generation and Editing

> [!NOTE]
>
> `step-2x-large` and `step-image-edit-2` were retired on October 10, 2026. The text-to-image, image-to-image, and image editing APIs have stopped serving requests. See the [image model retirement notice](https://platform.stepfun.ai/docs/en/guides/image-offline-notice.md).

### Pricing for Value-Added Capabilities

| Capability | Billing unit |
| :- | :- |
| Internet search | \$0.006 / call |
| Image search | \$0.02 / call |
| File storage | \$0.08 / GB / day |

Value-added capabilities are billed by actual usage.

## Tiered Rate Limits

Pay-as-you-go calls to the standard Open Platform API are rate limited by tier according to the cumulative top-up amount on your account. Only cash top-ups count toward that amount; vouchers do not. [Step Plan](https://platform.stepfun.ai/docs/en/step-plan/overview.md) usage is governed by the monthly Credit allowance of your subscribed tier rather than by cumulative top-up. When resources reach capacity, we may temporarily adjust the limits for each tier.

### Individual Accounts

Individual accounts must complete identity verification first. Tiers are assigned by cumulative top-up amount:

| User tier | Cumulative top-up amount | Concurrency | RPM | TPM |
| :-: | :- | :- | :- | :- |
| V0 | Under \$15 | 5 | 100 | 500,000 |
| V1 | \$15 to \$69 | 20 | 400 | 2,000,000 |
| V2 | \$70 to \$299 | 30 | 600 | 3,000,000 |
| V3 | \$300 to \$1,499 | 40 | 800 | 4,000,000 |
| V4 | \$1,500 and above | 130 | 2,600 | 13,000,000 |

### Enterprise Accounts

For the rate limit tiers available to verified enterprise accounts, contact your sales representative. Prepaid funds added to an Open Platform account count toward the cumulative top-up amount and are eligible for invoicing through the Open Platform. Postpaid billing is not tied to the cumulative top-up amount and is not invoiced through the Open Platform.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.