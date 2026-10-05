import json
from .common import fetch_text, number, observation, parse_or_archive, snapshot

SOURCE = "https://api.deepinfra.com/models/list"


def parse(body, aliases):
    models = json.loads(body)
    if not isinstance(models, list):
        raise ValueError("DeepInfra catalog must be an array")
    records = []
    for model in models:
        model_id = model.get("model_name")
        if model_id not in aliases:
            continue
        pricing = model["pricing"]
        if pricing.get("type") != "tokens" or pricing.get("table"):
            raise ValueError("Unsupported tiered/token pricing for {}".format(model_id))
        # API rates are cents/token; USD per million = cents/token * 10,000.
        input_price = number(pricing["cents_per_input_token"]) * 10000
        output_price = number(pricing["cents_per_output_token"]) * 10000
        cache = pricing.get("rate_per_input_token_cached")
        cache_write = pricing.get("rate_per_input_token_cache_write")
        tiers = [("standard", 1)]
        for tier in ("priority", "flex"):
            factor = pricing.get("rate_per_service_tier_" + tier)
            if factor is not None:
                tiers.append((tier, number(factor)))
        for tier, factor in tiers:
            records.append(observation(
                "deepinfra", model_id, round(input_price * factor, 10), round(output_price * factor, 10), SOURCE,
                cache_read_per_million=round(input_price * number(cache) * factor, 10) if cache is not None else None,
                cache_write_per_million=round(input_price * number(cache_write) * factor, 10) if cache_write is not None else None,
                context_window=model.get("max_tokens"), quantization=model.get("quantization"), service_tier=tier,
                variant="turbo" if model_id.lower().endswith("-turbo") else "standard"))
    return snapshot(records, body, SOURCE, authoritative=True)


def collect(aliases):
    return parse_or_archive(fetch_text(SOURCE), SOURCE, parse, aliases)
