import hashlib
from pathlib import Path
from urllib.parse import urlparse
import yaml
from providers.common import number

ROOT = Path(__file__).resolve().parents[1]
PRICE_FIELDS = ("input_per_million", "output_per_million", "cache_read_per_million", "cache_write_per_million")
OFFERING_FIELDS = ("model_id", "provider", "provider_model_id", "context_window", "quantization", "service_tier", "region", "variant", "source_url", "min_input_tokens", "max_input_tokens", "max_output_tokens", "pricing_notes")


def catalog(root=ROOT):
    models = yaml.safe_load((root / "catalog/models.yaml").read_text())["models"]
    ids = {model["id"] for model in models}
    if len(ids) != len(models):
        raise ValueError("Duplicate canonical model IDs")
    aliases = {}
    for canonical, entry in yaml.safe_load((root / "catalog/aliases.yaml").read_text()).items():
        if canonical not in ids:
            raise ValueError("Alias points to unknown canonical model {}".format(canonical))
        for alias in entry["aliases"] + [canonical]:
            if alias in aliases and aliases[alias] != canonical:
                raise ValueError("Ambiguous alias {}".format(alias))
            aliases[alias] = canonical
    return models, aliases


def normalize(record, aliases, observed_at, source_hash):
    model_id = aliases.get(record["provider_model_id"])
    if model_id is None:
        raise ValueError("Unknown model alias; add it manually before tracking")
    url = urlparse(record["source_url"])
    if url.scheme not in ("https", "http") or not url.hostname:
        raise ValueError("Every observation requires an official source URL")
    if record.get("currency") != "USD":
        raise ValueError("MVP supports USD prices only")
    context = record.get("context_window")
    if context is not None and (isinstance(context, bool) or not isinstance(context, int) or context <= 0):
        raise ValueError("Invalid context window")
    minimum = record.get("min_input_tokens", 0)
    maximum = record.get("max_input_tokens")
    output_limit = record.get("max_output_tokens")
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0:
        raise ValueError("Invalid minimum input token count")
    for limit in (maximum, output_limit):
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
            raise ValueError("Invalid token limit")
    if maximum is not None and maximum < minimum:
        raise ValueError("Invalid input pricing band")
    if not isinstance(record.get("pricing_notes", ""), str):
        raise ValueError("Invalid pricing notes")
    tier = record["service_tier"]
    if tier not in ("standard", "priority", "flex"):
        raise ValueError("Unknown service tier")
    for key in ("quantization", "variant", "region", "provider", "provider_model_id"):
        if record.get(key) is not None and not isinstance(record[key], str):
            raise ValueError("Invalid offering metadata: {}".format(key))
    identity = [record["provider"], model_id, record["provider_model_id"], tier, record["region"]]
    # Preserve all existing offering IDs; distinguish new prompt-length bands.
    if minimum or maximum is not None:
        identity.extend([str(minimum), str(maximum)])
    offering_id = record["provider"] + "-" + hashlib.sha256("\0".join(identity).encode()).hexdigest()[:16]
    offering = {key: record.get(key) for key in OFFERING_FIELDS}
    offering.update(min_input_tokens=minimum, pricing_notes=record.get("pricing_notes", ""))
    offering.update(id=offering_id, model_id=model_id, active=True, last_seen_at=observed_at)
    price = {key: None if record.get(key) is None else round(number(record[key]), 10) for key in PRICE_FIELDS}
    if price["input_per_million"] is None or price["output_per_million"] is None:
        raise ValueError("Input and output prices are required")
    price.update(offering_id=offering_id, observed_at=observed_at, currency="USD", source_url=record["source_url"], source_sha256=source_hash)
    return offering, price


def price_signature(price):
    return tuple(price.get(field) for field in PRICE_FIELDS) + (price["currency"],)
