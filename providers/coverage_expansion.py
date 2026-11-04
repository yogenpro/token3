"""Bounded public billing sources, with separately selected comparable quotes.

Document, image, credit and decision billing stays source-native. This registry
does not make a discovered model or a price-card label comparable automatically.
"""
import hashlib
import json
from dataclasses import dataclass

from .common import Collection, fetch_text, safe_error
from .pricing_api import encode_payload


@dataclass(frozen=True)
class PublicSource:
    provider: str
    name: str
    SOURCE: str
    documents: tuple = ()
    adapter: str = "public_documents"
    scope_note: str = ""

    def collect(self, aliases=None):
        payload = dict(format="token3.inventory-sources.v1", adapter=self.adapter,
                       scope_note=self.scope_note)
        urls = []
        if self.adapter != "public_documents":
            body = fetch_text(self.SOURCE)
            payload["catalog"] = json.loads(body)
            urls.append(self.SOURCE)
        documents = self.documents or ((self.SOURCE,) if self.adapter == "public_documents" else ())
        if documents:
            payload["documents"] = []
            for url in documents:
                body = fetch_text(url)
                payload["documents"].append(dict(source_url=url, body=body))
                urls.append(url)
        body = encode_payload(payload)
        records, error = [], None
        from .coverage_quotes import REVIEWED_PROVIDERS, reviewed_quotes
        reviewed = self.provider in REVIEWED_PROVIDERS
        if reviewed:
            try:
                records = reviewed_quotes(self.provider, payload, aliases or {})
            except Exception as exc:
                error = safe_error(exc)
        return Collection(records, self.SOURCE, hashlib.sha256(body.encode()).hexdigest(),
            source_payload=body, source_urls=urls, source_kind="documentation" if self.adapter == "public_documents" else "api+documentation" if documents else "api",
            inventory_only=not reviewed, parse_error=error)


PUBLIC_SOURCES = {
    "cohere": PublicSource("cohere", "Cohere", "https://cohere.com/pricing",
        documents=("https://docs.cohere.com/docs/models.md", "https://cohere.com/pricing"),
        scope_note="Public model directory and pricing page. Exact API IDs, deprecated entries and research models stay distinct. Pricing-card names do not bind a versioned API quote; Model Vault instance prices and search units are not token rates."),
    "ai21": PublicSource("ai21", "AI21", "https://www.ai21.com/pricing/",
        documents=("https://docs.ai21.com/docs/jamba-foundation-models.md", "https://www.ai21.com/pricing/"),
        scope_note="Public Jamba directory and direct pricing page. Generic Mini/Large labels do not establish the billing scope of a versioned Jamba endpoint. Cloud-host prices and free-trial credits stay separate."),
    "perplexity": PublicSource("perplexity", "Perplexity API", "https://docs.perplexity.ai/docs/getting-started/pricing.md",
        documents=("https://docs.perplexity.ai/docs/getting-started/pricing.md", "https://docs.perplexity.ai/docs/agent-api/models.md", "https://docs.perplexity.ai/docs/router/models.md"),
        scope_note="Public Agent, Orchestrator, search, embedding and decision billing. Orchestrator is private preview; its public documentation does not establish general access. Tool/request/session fees, tiers and token quotes stay separate."),
    "cerebras": PublicSource("cerebras", "Cerebras", "https://api.cerebras.ai/public/v1/models",
        documents=("https://inference-docs.cerebras.ai/api-reference/models/public-models.md", "https://inference-docs.cerebras.ai/models/overview.md", "https://inference-docs.cerebras.ai/models/qwen-3.8-27b.md", "https://inference-docs.cerebras.ai/models/openai-oss.md"), adapter="cerebras",
        scope_note="Complete unauthenticated Shared Inference model feed and selected model references. Free and paid limits can differ; conflicting feed/document limits remain explicit. Dedicated inference is a separate product."),
    "castform": PublicSource("castform", "Castform", "https://api.castform.com/v1/pricing", adapter="castform",
        scope_note="Complete public pricing response, retaining inference and training as different billing products. Advertised model identifiers establish this billing source only; upstream-provider pricing, limits and cache fees are not inferred."),
    "arcee": PublicSource("arcee", "Arcee AI", "https://docs.arcee.ai/get-started/pricing.md",
        scope_note="Public Arcee Platform rates. Exact served IDs are independent billing offers; creator names do not imply direct upstream-provider billing."),
    "stepfun": PublicSource("stepfun", "StepFun", "https://platform.stepfun.ai/docs/en/guides/pricing/details.md",
        scope_note="Global English pricing document, including text, image, audio and voice charges. Chinese-region billing, coding subscriptions and credits are separate products. Cache hit/miss and session rounding remain explicit."),
    "upstage": PublicSource("upstage", "Upstage", "https://www.upstage.ai/pricing/api",
        documents=("https://www.upstage.ai/pricing/api", "https://console.upstage.ai/docs/models.md", "https://console.upstage.ai/docs/models/solar-pro-4.md", "https://console.upstage.ai/docs/models/solar-mini-4.md"),
        scope_note="Direct API pricing and model references. Current Solar 4 versions, ended Solar 2/3 service, document pages, prepaid bonuses, VAT and Studio subscriptions stay distinct. No retrospective prices are imported."),
    "telnyx": PublicSource("telnyx", "Telnyx Inference", "https://telnyx.com/pricing/inference-api",
        scope_note="Public inference pricing document. Different deployment/pricing sections, promotional rows and cached-input rates are source-native; no cheapest-row selection or inferred endpoint IDs."),
    "typesafe": PublicSource("typesafe", "TypeSafe", "https://docs.typesafe.ai/models.md",
        scope_note="Jev typed-decision models; source-native input-token billing with explicitly free outputs and separate per-request/per-question limits. No assumed equivalence to general chat generation."),
    "blackforestlabs": PublicSource("blackforestlabs", "Black Forest Labs", "https://docs.bfl.ai/quick_start/pricing.md",
        scope_note="Public FLUX image pricing by model, resolution, image/token component and edit/generation scope. Credit, token and image formulas are not converted to text-generation quotes."),
    "runway": PublicSource("runway", "Runway", "https://docs.dev.runwayml.com/guides/pricing.md",
        scope_note="Public developer-API model prices and credit billing, including hosted third-party models. Native seconds, images, characters and credits remain separate; consumer subscription allowances are not API rates."),
    "stability": PublicSource("stability", "Stability AI", "https://platform.stability.ai/pricing",
        scope_note="Public API image, audio, 3D and editing credit tariffs. Native credit amounts and published conversion prose remain evidence, without inferred token rates or reviewed money conversion."),
    "ideogram": PublicSource("ideogram", "Ideogram", "https://developer.ideogram.ai/ideogram-api/api-overview",
        scope_note="Public API model/capability documentation and linked API billing information. Image resolution, rendering modes and consumer-plan credits do not establish text-token prices."),
    "elevenlabs": PublicSource("elevenlabs", "ElevenLabs", "https://elevenlabs.io/pricing/api",
        documents=("https://elevenlabs.io/pricing/api", "https://elevenlabs.io/docs/overview/models.md", "https://elevenlabs.io/docs/overview/administration/billing.md"),
        scope_note="Public API plan and billing documents, including audio, speech, music and other exposed products. Plan allowances, minimum purchases, character/token/second units and concurrency remain native; no flat universal rate is inferred."),
    "byteplus": PublicSource("byteplus", "BytePlus ModelArk", "https://docs.byteplus.com/docs/en/modelark/model-pricing.md",
        scope_note="International ModelArk tariff document. Exact dated IDs, prompt bands, Standard/Flex tiers, peak/off-peak schedules, cache-storage hours and audio/image/video/3D charges remain native. ByteDance is a creator; Chinese Volcano Engine billing is separate."),
    "adobe": PublicSource("adobe", "Adobe Firefly API", "https://developer.adobe.com/firefly-services/docs/firefly-api/guides/",
        scope_note="Public developer API guide, a bounded product/model-document scope. Monetary API tariffs and consumer subscription-credit equivalence remain unverified; the guide is not an authoritative complete model catalog."),
    "baidu": PublicSource("baidu", "Baidu Qianfan", "https://cloud.baidu.com/product/wenxinworkshop.html",
        scope_note="Public Qianfan product/model overview only. Tariff, currency and endpoint availability remain unverified. No Chinese-to-international billing equivalence, token prices or full-catalog completeness is inferred."),
}
