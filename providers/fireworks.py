import json
import os
import re
from decimal import Decimal

from .common import fetch_text, markdown_tables, number, observation, parse_or_archive, safe_error, snapshot
from .pricing_api import encode_payload, fetch_pages

API_URL = "https://api.fireworks.ai/v1/serverless/models"
SOURCE = "https://docs.fireworks.ai/serverless/pricing"
FETCH_URL = SOURCE + ".md"


def parse(body, aliases):
    records = []
    for header, cells in markdown_tables(body):
        if header != ["Model", "Standard", "Priority"]:
            continue
        match = re.search(r"https://app\.fireworks\.ai/models/([^/]+)/([^\s)]+)", cells[0])
        if not match:
            continue
        model_id = "accounts/{}/models/{}".format(*match.groups())
        if model_id not in aliases:
            continue
        for tier, cell in zip(("standard", "priority"), cells[1:]):
            prices = re.fullmatch(r"\s*\$([\d.]+)\s*/\s*\$([\d.]+)\s*/\s*\$([\d.]+)\s*", cell.replace("\\$", "$"))
            if not prices:
                raise ValueError("Fireworks price triple changed: {}".format(cell))
            input_price, cache, output = [number(x) for x in prices.groups()]
            records.append(observation("fireworks", model_id, input_price, output, SOURCE,
                                       cache_read_per_million=cache, service_tier=tier))
    # This is a headline-model pricing table, not an exhaustive availability API.
    return snapshot(records, body, SOURCE, authoritative=False)


def _api_money(amount):
    # The first-party FireConnect client documents flat USD decimal amounts.
    # Structured Money objects must establish USD explicitly.
    if not isinstance(amount, dict):
        return number(amount)
    if amount.get("currencyCode") != "USD":
        raise ValueError("Fireworks price currency must be explicitly USD")
    units, nanos = amount.get("units", "0"), amount.get("nanos", 0)
    if not re.fullmatch(r"-?\d+", str(units)) or isinstance(units, bool):
        raise ValueError("Invalid Fireworks whole money units")
    if isinstance(nanos, bool) or not isinstance(nanos, int) or abs(nanos) > 999999999:
        raise ValueError("Invalid Fireworks fractional money units")
    if (int(units) > 0 and nanos < 0) or (int(units) < 0 and nanos > 0):
        raise ValueError("Inconsistent Fireworks money signs")
    return number(Decimal(str(units)) + Decimal(nanos) / Decimal(1000000000))


def parse_api(body, aliases):
    payload = json.loads(body)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Fireworks serverless API is missing its data array")
    records = []
    sku_fields = {"LLM input tokens (uncached)": "input", "LLM input tokens (cached)": "cache", "LLM output tokens": "output"}
    for model in payload["data"]:
        model_id = model.get("id") or model.get("name")
        if model_id not in aliases:
            continue
        mode = model.get("serverless_mode")
        if mode in ("fast", "spot"):
            continue  # Archived, but not supported by the curated calculator.
        tier = {"default": "standard", "standard": "standard", "priority": "priority"}.get(mode)
        if tier is None:
            raise ValueError("Unknown Fireworks serving mode; cannot assume Standard")
        rates = {}
        for sku in model.get("pricing", []):
            field = sku_fields.get(sku.get("sku"))
            if field is None:
                continue
            if sku.get("unit") != "1M tokens":
                raise ValueError("Fireworks token rate must be quoted per 1M tokens")
            rate = _api_money(sku.get("amount"))
            if field in rates:
                raise ValueError("Duplicate Fireworks token price dimension")
            rates[field] = rate
        if not {"input", "output"}.issubset(rates):
            raise ValueError("Incomplete Fireworks token prices")
        invocation = model.get("usage_identifier") or model_id
        records.append(observation("fireworks", model_id, rates["input"], rates["output"], API_URL,
            cache_read_per_million=rates.get("cache"), service_tier=tier,
            context_window=model.get("context_length"),
            pricing_notes="Fireworks serverless catalog API USD/1M token rates; serving mode {}. Invocation identifier: {}. Fast/Spot and non-token prices are retained only in the raw inventory.".format(mode, invocation)))
    return snapshot(records, body, API_URL, source_kind="api")


def collect(aliases):
    key = os.environ.get("FIREWORKS_API_KEY", "").strip()
    reason = "FIREWORKS_API_KEY not configured"
    if key:
        try:
            payload, urls = fetch_pages(API_URL, "data", {"Authorization": "Bearer " + key},
                                        token_keys=("nextPageToken", "next_page_token"))
            body = encode_payload(payload)
        except Exception as exc:
            reason = "Fireworks pricing API unavailable: " + safe_error(exc, [key])
        else:
            result = parse_or_archive(body, API_URL, parse_api, aliases)
            result.source_kind = "api"
            result.source_urls = urls
            return result
    result = parse_or_archive(fetch_text(FETCH_URL), SOURCE, parse, aliases)
    result.source_urls = [FETCH_URL]
    result.source_kind = "documentation"
    result.fallback_reason = reason
    return result
