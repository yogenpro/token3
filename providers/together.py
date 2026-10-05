import json
import os

from .common import fetch_text, markdown_tables, money, number, observation, parse_or_archive, safe_error, snapshot

API_URL = "https://api.together.ai/v1/models"
SOURCE = "https://docs.together.ai/docs/serverless-models"
FETCH_URL = SOURCE + ".md"


def parse(body, aliases):
    records = []
    for header, cells in markdown_tables(body):
        if "API model string" not in header or "Input pricing (per 1M tokens)" not in header:
            continue
        row = dict(zip(header, cells))
        model_id = row["API model string"].strip("`")
        if model_id not in aliases:
            continue
        context = row["Context length"].replace(",", "")
        records.append(observation(
            "together", model_id,
            money(row["Input pricing (per 1M tokens)"]),
            money(row["Output pricing (per 1M tokens)"]), SOURCE,
            cache_read_per_million=money(row.get("Cached input pricing (per 1M tokens)", "-"), optional=True),
            context_window=int(context),
            quantization=None if row.get("Quantization", "-") == "-" else row["Quantization"],
            variant="turbo" if "turbo" in model_id.lower() else "standard"))
    return snapshot(records, body, SOURCE, authoritative=False)


def parse_api(body, aliases):
    models = json.loads(body)
    if not isinstance(models, list) or any(not isinstance(model, dict) for model in models):
        raise ValueError("Together models API must return a model array")
    records = []
    for model in models:
        model_id = model.get("id")
        if model_id not in aliases:
            continue
        if model.get("type") not in ("chat", "language"):
            raise ValueError("Tracked Together model is not a text-token offering")
        rates = model["pricing"]
        records.append(observation("together", model_id, number(rates["input"]), number(rates["output"]), API_URL,
            cache_read_per_million=number(rates["cached_input"]) if rates.get("cached_input") is not None else None,
            context_window=model.get("context_length"), quantization=model.get("quantization"),
            variant="turbo" if "turbo" in model_id.lower() else "standard",
            pricing_notes="Together List Models API text rates in USD/1M tokens. Other modality, base, hourly and fine-tuning rates remain in the raw inventory; they are not token prices."))
    # Authentication may scope visibility. Absence must not retire offerings.
    return snapshot(records, body, API_URL, source_kind="api")


def collect(aliases):
    key = os.environ.get("TOGETHER_API_KEY", "").strip()
    reason = "TOGETHER_API_KEY not configured"
    if key:
        try:
            body = fetch_text(API_URL, headers={"Authorization": "Bearer " + key})
        except Exception as exc:
            reason = "Together pricing API unavailable: " + safe_error(exc, [key])
        else:
            result = parse_or_archive(body, API_URL, parse_api, aliases)
            result.source_kind = "api"
            result.source_urls = [API_URL]
            return result
    result = parse_or_archive(fetch_text(FETCH_URL), SOURCE, parse, aliases)
    result.source_urls = [FETCH_URL]
    result.source_kind = "documentation"
    result.fallback_reason = reason
    return result
