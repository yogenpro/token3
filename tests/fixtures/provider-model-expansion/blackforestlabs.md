> ## Documentation Index
> Fetch the complete documentation index at: https://docs.bfl.ml/llms.txt
> Use this file to discover all available pages before exploring further.

# Overview

> Credit-based pricing for all FLUX models including FLUX 3, FLUX.2, FLUX.1, and batch requests. 1 credit equals $0.01 USD.

> [!NOTE]
>
> **Simple credit-based pricing:** 1 credit = \$0.01 USD • Pay per image, or per second for video • Same price for API and Playground

## Pricing

The following table shows pricing for all FLUX models and their variants:

### FLUX 3 Video

Use the [FLUX 3 video pricing calculator](https://bfl.ai/pricing?category=flux+3+video) to calculate the cost of your video.

FLUX 3 generates video with synchronized audio and uses **per-second pricing** — cost scales with clip length, resolution (`hd`, `fhd`, `qhd`, or `uhd`), and whether you run a full render or a fast [draft](https://docs.bfl.ml/flux_3/flux3_overview.md#draft-mode).

Full-render rates are per second of output, by resolution class:

| Mode | `hd` | `fhd` | `qhd` | `uhd` | Draft |
| - | - | - | - | - | - |
| Text to Video (`t2v`) | | | | | |
| Image to Video (`i2v`) | | | | | |
| Video Continuation (`v2v`) | | | | | |

> [!NOTE]
>
> Drafts render at `hd`. Use the published draft rates above to estimate the cost of exploring variants before you enhance the shot you keep. `fhd`, `qhd`, and `uhd` are the same generation finished by the video upsampler at a larger canvas — see [delivered dimensions](https://docs.bfl.ml/flux_3/flux3_video.md#resolution) — and are billed at the delivered class. See the [FLUX 3 overview](https://docs.bfl.ml/flux_3/flux3_overview.md#specifications) for length limits and supported aspect ratios.

### FLUX 3 Image

[FLUX 3 Image](https://docs.bfl.ml/flux_3/flux3_image_generate.md) is priced per image by `resolution`:

| `resolution` | Output size | Price per image |
| - | - | - |
| `768sq` | 768 × 768 | |
| `1k` | About 1 megapixel | |
| `1.5k` | About 2 megapixels | |
| `2k` | About 4 megapixels | |
| `4k` | About 16 megapixels | |

Requests with `width` and `height`, or with `resolution` set to `match_input`, are billed at the smallest tier with at least as many pixels. Anything above about 4 megapixels is billed at the `4k` price.

The submission response includes the `cost` of each request.

### FLUX 3 Image Klein

[FLUX 3 Image Klein](https://docs.bfl.ml/flux_3/flux3_image_klein.md) is priced per image by output resolution. Text to image and image editing cost the same.

| | 768 × 768 | 1K | 1.5K | 2K | 4K |
| - | - | - | - | - | - |
| **FLUX 3 Klein** | | | | | |

### FLUX Tools (Video)

[FLUX Video Upscale](https://docs.bfl.ml/flux_tools/flux_video_upscale.md) is priced **per output megapixel-second**: the megapixels per output frame multiplied by the output duration in seconds.

| Variant | Price |
| - | - |
| FLUX Video Upscale (Precise) |  per megapixel-second¹ ² ³ ⁴ |
| FLUX Video Upscale (Creative) |  per megapixel-second¹ ² ³ ⁴ |

¹ One megapixel-second is one megapixel (1,048,576 pixels, i.e. 1024 × 1024) of output resolution for one second of output video. Charges are calculated on the delivered output's actual frame dimensions and duration: megapixels per output frame × output duration in seconds, with fractional values charged pro rata. Example: upscaling a 10-second clip to 1080p (1920 × 1080 = 1.98 megapixels) is approximately 19.8 megapixel-seconds, i.e.  (Precise) or  (Creative).

² Charges are based on output only. Input resolution, upscale factor and optional prompts are not charged separately.

³ Rates apply to output at the standard frame rate of 24 frames per second. Where output at a higher frame rate is requested and supported, charges scale proportionally with frame rate (equivalently, the listed rate ÷ 24 per megapixel per frame). Supported input durations, resolutions, upscale factors and frame rates are set out in the [documentation](https://docs.bfl.ml/flux_tools/flux_video_upscale.md).

⁴ Input videos up to 20 seconds. Sources longer than 20 seconds are rejected before processing; they are not truncated, and no charge applies.

[FLUX Video Edit](https://docs.bfl.ml/flux_tools/flux_video_edit.md) \[fast] is priced **per second of output video**. The output keeps the source clip's length.

| Variant | Price |
| - | - |
| FLUX Video Edit \[fast] |  per second |

### FLUX.2 Models

FLUX.2 uses **megapixel-based pricing** — cost scales with output resolution.

| Model | Text-to-Image | Image Editing | Best For |
| - | - | - | - |
| FLUX.2 \[klein] 4B | from  | from  | Real-time, high volume |
| FLUX.2 \[klein] 9B | from  | from  | Balanced quality/speed |
| FLUX.2 \[pro] | from  | from  | Production workflows, fast turnaround |
| FLUX.2 \[max] | from  | from  | Highest quality, grounding search |
| FLUX.2 \[flex] | from  | from  | Fine-grained control, typography |
| FLUX.2 \[dev] | Local only | Local only | Open weights, non-commercial (no hosted API) |

> [!NOTE]
>
> **Klein pricing explained:** The first megapixel costs a flat rate, then each additional MP adds to the total. For example, a 2MP image with Klein 4B costs  +  = .

> [!NOTE]
>
> FLUX.2 pricing varies by output resolution. Use the [pricing calculator](https://bfl.ai/pricing) for exact costs.

### Fine-tuned Endpoints (Public Beta)

During public beta, fine-tuned FLUX.2 endpoints are billed at the **same rate as their base endpoints**. For example, a request to `flux-2-klein-9b-kv-finetuned` costs the same as the equivalent `flux-2-klein-9b` request at the same resolution.

| Endpoint | Base Endpoint | Beta Pricing |
| - | - | - |
| `flux-2-klein-9b-kv-finetuned` | `flux-2-klein-9b` | from  |

> [!NOTE]
>
> Pricing for fine-tuned endpoints may change once out of public beta. See the [LoRA inference guide](https://docs.bfl.ml/flux_2/flux2_lora_inference) for details on how to call these endpoints.

### FLUX.1 Models (Previous Generation)

| Model | Credits per Image | Price per Image | Description |
| - | - | - | - |
| FLUX.1 Kontext \[pro] |  credits | | Create and edit images with text and images |
| FLUX.1 Kontext \[max] |  credits | | Create and edit images with text and images, maximum quality |
| | | | |
| FLUX1.1 \[pro] |  credits | | The standard for text-to-image generation with fast, reliable and consistently stunning results |
| FLUX1.1 \[pro] Ultra |  credits | | Ultra-high-resolution image creation - with more pixels in every picture |
| FLUX1.1 \[pro] Raw |  credits | | High-quality, with a genuine feel of candid photography |
| FLUX.1 Fill \[pro] |  credits | | Targeted and fast text-driven image inpainting |
| | | | |

## Batch Pricing

> [!TIP]
>
> **Batch requests multiply the base cost by the number of images**

**Example:** FLUX.2 \[pro] batch of 4 images

* Single image: from&#x20;
* Batch of 4: from&#x20;

## Getting Started

> [card] [Quick Start](https://docs.bfl.ml/quick_start/get_started.md)
>
> Create account, add credits, and get API keys

> [card] [Generate Images](https://docs.bfl.ml/quick_start/generating_images)
>
> Start creating with our API

> [card] [Try Playground](https://playground.bfl.ai)
>
> Try our models without writing code


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.