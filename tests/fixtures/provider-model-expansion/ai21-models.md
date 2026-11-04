> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ai21.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Jamba

> Introducing the Jamba Family of Open Models.

## Overview

Built on the novel Mamba-Transformer architecture, these highly efficient and powerful models push the boundaries of AI. They deliver unmatched speed and quality and feature the longest context window (256K tokens) among open models.

> [card] Jamba Large
>
> Our most powerful and advanced model, designed to handle complex tasks at enterprise scale with superior performance.

> [card] Jamba2 Mini
>
> Jamba2 Mini blends efficiency and steerability into a 12B-active parameters model, delivering reliable output on core enterprise workflows.

> [card] Jamba2 3B
>
> Jamba2 3B packs reliability and steerability into a compact 3B model, powering on-device applications and supporting agentic systems.

## Key Benefits

> [card] Privately deployable without compromising on quality
>
> Retain total control over your data, with zero data visibility for the model vendor by deploying Jamba privately in your VPC or on-premises. Ideal for organizations or use cases handling regulated data (e.g., in finance or healthcare) or confidential proprietary data. With comparable quality to market-leading models, you get superior quality with total data privacy.

> [card] Open models
>
> With the weights available to be downloaded into your environment, Jamba can be customized to your domain and use case. This is a model that's fully yours.

> [card] Long context performance
>
> With a 256K context window, Jamba excels on the kinds of use cases enterprises rely on in their workflows, from analyzing lengthy documents to enhancing RAG workflows at the retrieval stage. And due to its efficiency-optimized hybrid architecture, it can do all this at a lower cost than competitors.

## Self Deployment Options

Jamba models are ideal for enterprises that need to maintain full control over data and performance. Deployment options include:

* **Cloud-hosted VPC** – Isolate and scale your deployment in a virtual private cloud environment.
* **On-premises environments** – Run Jamba entirely within your own infrastructure to meet strict compliance or latency requirements.
* **Custom hybrid solutions** – Combine cloud and on-premises capabilities to fit your architecture, performance, and governance needs.

## Supported Languages

Jamba models officially support 9 languages:

* English, Spanish, French, Portuguese, Italian, Dutch, German, Arabic, Hebrew.

## Model Details

| Model | Model Size | Max Tokens | Version | Snapshot | API Endpoint |
| - | - | - | - | - | - |
| Jamba Large | 398B parameters (94B active) | 256K | 1.7 | 2025-07 | `jamba-large` |
| Jamba Mini | 52B parameters (12B active) | 256K | 2 | 2026-01 | `jamba-mini` |
| Jamba 3B | 3B parameters | 256K | 2 | 2026-01 | N/A |

Engineers and data scientists at AI21 labs created the model to help developers and businesses leverage AI to build real-world products with tangible value. The Jamba model family supports multi-language and zero-shot instruction-following.

* **Organization developing model:** AI21 Labs
* **Model type:** Joint Attention and Mamba (Jamba)
* **Knowledge cutoff date** August 22nd, 2024
* **Input Modality:** Text
* **Output Modality:** Text
* **Contact:** [info@ai21.com](mailto:info@ai21.com)

## API Versioning

We advise using dated versions of the Jamba API to avoid disruptions from model updates and breaking changes.

Here are the details of the available versions:

* `jamba-large` currently points to `jamba-large-1.7-2025-07`
* `jamba-mini` currently points to `jamba-mini-2-2026-01`
* `jamba-large-1.7` points to `jamba-large-1.7-2025-07`
* `jamba-mini-2` points to `jamba-mini-2-2026-01`

## Model Deprecation

| Model | Snapshot | API Endpoint | Deprecation Date |
| - | - | - | - |
| Jamba Mini 1.7 | 2025-07 | `jamba-mini-1.7-2025-08` | 2026-02-01 |
| Jamba Large 1.6 | 2025-03 | `jamba-large-1.6-2025-03` | 2025-08-03 |
| Jamba Mini 1.6 | 2025-03 | `jamba-mini-1.6-2025-03` | 2025-08-03 |
| Jamba Large 1.5 | 2024-08 | `jamba-large-1.5-2024-08` | 2025-05-06 |
| Jamba Mini 1.5 | 2024-08 | `jamba-mini-1.5-2024-08` | 2025-05-06 |

## Model Compliance and Certifications

* [**SOC 2 compliance**](https://www.ai21.com/blog/soc-2-report)
* **ISO 27001, ISO 27017, and ISO 27018 certifications**
* [**Trust Center**](https://trust.ai21.com/?_gl=1*l2aasw*_gcl_aw*R0NMLjE3NDMzMTc1MTkuQ2owS0NRand0SjZfQmhEV0FSSXNBR2FubUtleDU5blZFaW9lRWctVG5HQno3Q092d2RoSUluVWpUdURPRWR1My1BdlBhRURGcWY0LVFzY2FBaFduRUFMd193Y0I.*_gcl_au*MTgyMTk2NzA0MS4xNzQyMjg0MjU3)

## Ethical Considerations

AI21 Labs is on a mission to supercharge human productivity with machines working alongside humans as thought partners, thereby promoting human welfare and prosperity. To deliver its promise, this technology must be deployed and used in a responsible and sustainable way, taking into consideration potential risks, including malicious use by bad actors, accidental misuse, and broader societal harms. We take these risks extremely seriously and put measures in place to mitigate them.

AI21 provides open access to Jamba that can be used to power a large variety of useful applications. We believe it is important to ensure that this technology is used in a responsible way, while allowing developers the freedom they need to experiment rapidly and deploy solutions at scale. Overall, we view the safe implementation of this technology as a partnership and collaboration between AI21 and our customers and encourage engagement and dialogue to raise the bar on responsible usage.

In order to use Jamba, you are required to comply with our [Terms of Service](https://lp.ai21.com/hubfs/resources/AI21-Models-Terms-of-Service.pdf?_gl=1*jr1jnx*_gcl_au*MTg4MDYzNjU4MC4xNzM0NTA4MjE4) and with the following [Usage Guidelines](https://docs.ai21.com/docs/responsible-use-1.md#usage-guidelines).

Please check these usage guidelines periodically, as they may be updated from time to time. For any questions, clarifications or concerns, please contact [safety@ai21.com.](mailto:safety@ai21.com)

## Limitations

There are a number of limitations inherent to neural networks technology that apply to Jamba. These limitations require explanation and carry important caveats for the application and usage of Jamba.

* **Accuracy:** Jamba, like other large pretrained language models, lacks important context about the world because it is trained on textual data and is not grounded in other modalities of experience such as video, real-world physical interaction, and human feedback. Like all language models, Jamba is far more accurate when responding to inputs similar to its training datasets. Novel inputs tend to generate higher variance in its output.
* **Coherence and consistency:** Responses from Jamba are sometimes inconsistent, contradictory, or contain seemingly random sentences and paragraphs.
* **Western/English bias:** Jamba is trained primarily on English-language text from the internet, and is best suited to classifying, searching, summarizing, and generating English text. Furthermore, Jamba has a tendency to hold and amplify the biases contained in its training dataset. As a result, groups of people who were not involved in the creation of the training data can be underrepresented, and stereotypes and prejudices can be perpetuated. Racial, religious, gender, socioeconomic, and other categorizations of human groups can be considered among these factors.
* **Explainability:** It is difficult to explain or predict how Jamba will respond without additional training and fine tuning. This is a common issue with neural networks of this scope and scale.
* **Recency:** Jamba was trained on a dataset created in March 2024, and therefore has no knowledge of events that have occurred after that date. We update our models regularly to keep them as current as possible, but there are notable gaps and inaccuracies in responses as a result of this lack of recency.

**Ready to take your projects to the next level?**\
Access Jamba via the [AI21 Studio API](https://docs.ai21.com/reference/jamba-1-6-api-ref.md) or [deploy privately](https://docs.ai21.com/docs/self-deployment).\
See our [Quick Start Guide](https://docs.ai21.com/docs/sdk.md) for integration steps, SDKs, and sample code.\
Explore Jamba in action on the [AI21 Studio Playground](https://studio.ai21.com/v2?tab=jamba_playground).
