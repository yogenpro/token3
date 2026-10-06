"""Collection-only official price sources. No inference calls or model aliases.

These sources enrich the source-native inventory; they deliberately do not
produce dashboard quotes. A gateway catalog is not a direct-provider quote.
"""
import hashlib
import io
import json
import re
from dataclasses import dataclass
from urllib.parse import urlencode

from .common import Collection, fetch_bytes, fetch_text, safe_error
from .pricing_api import MAX_CATALOG_BYTES, encode_payload

ENVELOPE = "token3.inventory-sources.v1"
SCW_CATEGORIES = ("Generative APIs", "Inference Dedicated")


def _listing(url, key="data"):
    payload = json.loads(fetch_text(url))
    items = payload if key is None else payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items or any(not isinstance(item, dict) for item in items):
        raise ValueError("Public catalog lacks a nonempty object listing")
    if isinstance(payload, dict):
        links = payload.get("links") or {}
        if payload.get("has_more") or payload.get("nextPageToken") or links.get("next"):
            raise ValueError("Public catalog pagination changed; refusing an incomplete listing")
        if "total_count" in payload and payload["total_count"] != len(items):
            raise ValueError("Public catalog total does not match the complete listing")
    return payload


def _scaleway(url):
    products, urls, expected, seen, size = [], [], None, set(), 0
    for page in range(1, 101):
        page_url = url + ("&" if "?" in url else "?") + urlencode({"page": page})
        body = fetch_text(page_url)
        size += len(body.encode())
        if size > MAX_CATALOG_BYTES:
            raise ValueError("Scaleway public catalog exceeds the collection limit")
        payload = json.loads(body)
        rows = payload.get("products")
        total = payload.get("total_count")
        if not isinstance(rows, list) or not rows or isinstance(total, bool) or not isinstance(total, int) or total <= 0:
            raise ValueError("Scaleway catalog has invalid pagination")
        if expected is None:
            expected = total
        if total != expected:
            raise ValueError("Scaleway catalog total changed during pagination")
        for item in rows:
            sku = item.get("sku") if isinstance(item, dict) else None
            if not sku or sku in seen:
                raise ValueError("Scaleway catalog repeated or omitted a SKU")
            seen.add(sku)
            if item.get("product_category") in SCW_CATEGORIES:
                products.append(item)
        urls.append(page_url)
        if len(seen) >= expected:
            if len(seen) != expected or not products:
                raise ValueError("Scaleway catalog is incomplete or has no selected AI SKUs")
            return dict(products=products, selected_categories=list(SCW_CATEGORIES),
                        complete_catalog_count=expected, page_count=len(urls)), urls
    raise ValueError("Scaleway catalog exceeded 100 pages")


def _oracle(url):
    payload = json.loads(fetch_text(url))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list) or not payload["items"]:
        raise ValueError("Oracle public price list is empty")
    if payload.get("hasMore") or payload.get("next") or payload.get("nextPageToken"):
        raise ValueError("Oracle public price list pagination changed")
    items = [row for row in payload["items"] if isinstance(row, dict)
             and "generative ai" in row.get("displayName", "").lower()]
    if not items:
        raise ValueError("Oracle public price list has no Generative AI SKUs")
    return dict(items=items, selected_service="OCI Generative AI", currency="USD")


def _snowflake_pdf(url):
    # PDF extraction retains page text and the exact response-byte hash. It is
    # not a table alignment guess or a credits-to-USD conversion.
    from pypdf import PdfReader
    body = fetch_bytes(url)
    if not body.startswith(b"%PDF-"):
        raise ValueError("Snowflake consumption table is not a PDF")
    reader = PdfReader(io.BytesIO(body))
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
        raise ValueError("Unsupported Snowflake consumption PDF")
    pages, total = [], 0
    for number, page in enumerate(reader.pages, 1):
        content = page.extract_text(extraction_mode="layout") or ""
        total += len(content.encode())
        if total > 8 * 1024 * 1024:
            raise ValueError("Snowflake extracted PDF exceeds the text limit")
        pages.append(dict(page=number, text=content))
    if not any(re.search(r"Cortex|Snowflake AI|AI Features", p["text"], re.I) for p in pages):
        raise ValueError("Snowflake PDF lacks the expected AI consumption tables")
    return dict(source_url=url, response_sha256=hashlib.sha256(body).hexdigest(),
                extraction="pypdf layout text; table alignment and model equivalence unreviewed",
                page_count=len(pages), pages=pages)


@dataclass(frozen=True)
class InventoryCollector:
    provider: str
    name: str
    SOURCE: str
    adapter: str = "documents"
    documents: tuple = ()
    scope_note: str = ""
    pdf_url: str = ""

    def collect(self, aliases=None):
        payload = dict(format=ENVELOPE, adapter=self.adapter, scope_note=self.scope_note)
        urls, fallback = [], None
        if self.adapter == "scaleway":
            payload["catalog"], urls = _scaleway(self.SOURCE)
        elif self.adapter == "oracle":
            payload["catalog"] = _oracle(self.SOURCE)
            urls = [self.SOURCE]
        elif self.adapter != "documents":
            key = None if self.adapter in ("nebius", "ovhcloud") else "data"
            payload["catalog"] = _listing(self.SOURCE, key)
            urls = [self.SOURCE]
        docs = []
        for url in self.documents or ((self.SOURCE,) if self.adapter == "documents" else ()):
            body = fetch_text(url)
            if not re.search(r"pric|bill|credit|token|neuron|DBU", body, re.I):
                raise ValueError("Official document lacks expected billing content")
            docs.append(dict(source_url=url, body=body))
            urls.append(url)
        if docs:
            payload["documents"] = docs
        if self.pdf_url:
            try:
                payload["pdf_document"] = _snowflake_pdf(self.pdf_url)
                urls.append(self.pdf_url)
            except Exception as error:
                fallback = "Model-rate consumption PDF unavailable; billing-guide coverage only. " + safe_error(error)
                payload["coverage"] = "billing_guide_only; model rates unavailable"
        body = encode_payload(payload)
        kind = "api+documentation" if self.adapter != "documents" and docs else "documentation" if self.adapter == "documents" else "api"
        return Collection([], self.SOURCE, hashlib.sha256(body.encode()).hexdigest(), source_payload=body,
                          source_urls=urls, source_kind=kind, fallback_reason=fallback, inventory_only=True,
                          source_evidence=[{key:payload['pdf_document'][key] for key in ('source_url', 'response_sha256')}]
                          if 'pdf_document' in payload else None)


INVENTORY_PROVIDERS = {
    "openrouter": InventoryCollector("openrouter", "OpenRouter", "https://openrouter.ai/api/v1/models", "openrouter",
        scope_note="Public advertised model catalog; prices can be route-dependent. Dynamic -1 prices are unknown, not free. Per-provider endpoint listings and credit-purchase fees are outside this source."),
    "vercel": InventoryCollector("vercel", "Vercel AI Gateway", "https://ai-gateway.vercel.sh/v1/models", "vercel",
        scope_note="Public gateway catalog, all exposed modalities and billing rules. Provider-dependent and regional pricing remain explicit; not proof of a selected upstream route."),
    "alibaba": InventoryCollector("alibaba", "Alibaba Cloud Model Studio", "https://docs.modelstudio.console.alibabacloud.com/en/model-studio/model-pricing.md",
        scope_note="Public Model Studio standard-price document, all returned regional tabs and modalities. Qwen is a model family, not a separate billing provider; console-only promotions are excluded."),
    "huggingface": InventoryCollector("huggingface", "Hugging Face Inference", "https://router.huggingface.co/v1/models", "huggingface",
        documents=("https://huggingface.co/docs/inference-providers/pricing",),
        scope_note="Complete public OpenAI-compatible chat model/provider routes plus the billing guide. Not the entire multimodal Hub model inventory. hf-inference compute seconds and illustrative hardware costs are not flat token rates."),
    "snowflake": InventoryCollector("snowflake", "Snowflake Cortex", "https://docs.snowflake.com/en/user-guide/snowflake-cortex/pricing.md",
        scope_note="AI and Platform Credits remain distinct. Consumption PDF pages are retained as unreviewed source text, not guessed model rows or converted USD quotes.",
        pdf_url="https://www.snowflake.com/legal-files/CreditConsumptionTable.pdf"),
    "cloudflare": InventoryCollector("cloudflare", "Cloudflare Workers AI", "https://developers.cloudflare.com/workers-ai/platform/pricing/index.md",
        scope_note="Public Workers AI price tables and neuron billing rules, including non-token modalities. Neurons and tokens are not assumed interchangeable."),
    "databricks": InventoryCollector("databricks", "Databricks", "https://www.databricks.com/product/pricing/foundation-model-serving",
        documents=("https://www.databricks.com/product/pricing/foundation-model-serving", "https://www.databricks.com/product/pricing/proprietary-foundation-model-serving"),
        scope_note="Public open and proprietary foundation-model serving tables. DBUs per token and capacity are retained; cloud/region/edition and USD-per-DBU conversions require separate review."),
    "oracle": InventoryCollector("oracle", "Oracle Cloud Generative AI", "https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/?currencyCode=USD", "oracle",
        scope_note="All Generative AI SKUs in the public USD OCI price list, with native metric, price model and dedicated-capacity rates; no inferred character-to-token conversion."),
    "nebius": InventoryCollector("nebius", "Nebius Token Factory", "https://tokenfactory.nebius.com/api/public/models_info", "nebius",
        scope_note="Public Token Factory catalog, every exposed flavor and region. No private custom models, GPU infrastructure price list or performance benchmark collection."),
    "xai": InventoryCollector("xai", "xAI", "https://docs.x.ai/developers/pricing",
        scope_note="Official public text, image, video, voice and tool pricing, including prompt-length rules and regional/batch modifiers. Account-authenticated model pricing is not collected without a separate reviewed source."),
    "zai": InventoryCollector("zai", "Z.ai", "https://docs.z.ai/guides/overview/pricing.md",
        scope_note="International Z.AI public API pricing in USD, with promotions and native tool/storage rules. Chinese Zhipu billing and subscription Coding Plans are separate products."),
    "ovhcloud": InventoryCollector("ovhcloud", "OVHcloud AI Endpoints", "https://catalog.endpoints.ai.ovh.net/rest/v1/models_v2", "ovhcloud",
        scope_note="Complete public AI Endpoints catalog, including unavailable entries. Prices retain native units; the JSON does not identify currency, so no currency is invented from a locale or another product page."),
    "scaleway": InventoryCollector("scaleway", "Scaleway Generative APIs", "https://api.scaleway.com/product-catalog/v2alpha1/public-catalog/products?page_size=1000", "scaleway",
        scope_note="Complete public SKU pagination, selecting Generative APIs and Inference Dedicated categories. EUR money, native unit sizes and locality are preserved; node prices are not assumed hourly."),
    "minimax": InventoryCollector("minimax", "MiniMax", "https://platform.minimax.io/docs/guides/pricing-paygo.md",
        scope_note="International pay-as-you-go API prices across published modalities. Subscription/Token Plans and Chinese-region billing are separate products; discounts and prompt bands remain native expressions."),
    "deepseek": InventoryCollector("deepseek", "DeepSeek", "https://api-docs.deepseek.com/quick_start/pricing",
        scope_note="Official public API model/price table with cache hit/miss, output and model-version conditions. Row/column orientation is source-native, not guessed canonical model equivalence."),
}
