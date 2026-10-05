import json
from .common import fetch_text, number, observation, parse_or_archive, snapshot

SOURCE = "https://api.novita.ai/v3/openai/models"


def parse(body, aliases):
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
            context_window=model.get("context_size"), quantization=model.get("quantization")))
    return snapshot(records, body, SOURCE, authoritative=True)


def collect(aliases):
    return parse_or_archive(fetch_text(SOURCE), SOURCE, parse, aliases)
