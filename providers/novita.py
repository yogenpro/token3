import json
from .common import fetch_text, number, observation, parse_or_archive, provider_aliases, snapshot

SOURCE = "https://api.novita.ai/v3/openai/models"


def parse(body, aliases):
    aliases = provider_aliases(aliases, "novita")
    payload = json.loads(body)
    models = payload["data"]
    if not isinstance(models, list):
        raise ValueError("Novita catalog must contain a data array")
    records = []
    for model in models:
        model_id = model.get("id")
        if model_id not in aliases:
            continue
        if model.get("is_tiered_billing"):
            raise ValueError("Tiered Novita billing needs an explicit parser: {}".format(model_id))
        # Prefer explicit USD decimal strings. The similarly named integer fields
        # use provider-specific billing units and must not be mistaken for USD.
        pricing = model["pricing"]
        records.append(observation(
            "novita", model_id,
            number(pricing["prompt"]["price_per_m_decimal"]),
            number(pricing["completion"]["price_per_m_decimal"]), SOURCE,
            cache_read_per_million=number(pricing["input_cache_read"]["price_per_m_decimal"]) if "input_cache_read" in pricing else None,
            cache_write_per_million=number(pricing["input_cache_write"]["price_per_m_decimal"]) if "input_cache_write" in pricing else None,
            context_window=model.get("context_size"), quantization=model.get("quantization"),
            pricing_notes="Novita explicit USD-per-million token decimal fields, not integer billing units. Published cache prices are separate; missing cache prices/TTL remain unverified. Cache writes, tool fees and other modalities are excluded from estimates."))
    return snapshot(records, body, SOURCE, authoritative=True)


def collect(aliases):
    return parse_or_archive(fetch_text(SOURCE), SOURCE, parse, aliases)
