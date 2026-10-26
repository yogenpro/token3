import hashlib
from pathlib import Path
from urllib.parse import urlparse
import yaml
from providers.common import number

ROOT = Path(__file__).resolve().parents[1]
PRICE_FIELDS = ("input_per_million", "output_per_million", "cache_read_per_million", "cache_write_per_million")
OFFERING_FIELDS = ("model_id", "provider", "provider_model_id", "context_window", "quantization", "service_tier", "region", "variant", "source_url", "min_input_tokens", "max_input_tokens", "max_output_tokens", "pricing_notes")


LEGACY_REVIEWED_PROVIDERS = frozenset(("deepinfra", "novita", "together", "fireworks", "groq", "openai", "anthropic", "gemini", "vertex", "bedrock", "azure"))
# Freeze the exemption to actual historical identities. Omitting source bindings
# on a future model must not accidentally enroll it as a legacy model.
LEGACY_REVIEWED_MODELS = frozenset((
    "openai/gpt-oss-120b", "openai/gpt-oss-20b", "meta/llama-3.3-70b-instruct", "meta/llama-3.1-8b-instruct",
    "qwen/qwen3-235b-a22b-instruct-2507", "openai/gpt-5.4", "openai/gpt-5.4-mini",
    "anthropic/claude-sonnet-4.6", "anthropic/claude-opus-4.6", "anthropic/claude-haiku-4.5",
    "google/gemini-3.8-flash", "google/gemini-3.5-flash-lite",
))


class ReviewedAliases(dict):
    """Identity aliases are not permission to review every provider's price.

    Historical bindings remain unchanged. New models explicitly enumerate
    reviewed provider/source IDs; the same ID in another feed stays native-only.
    """
    def __init__(self):
        super().__init__()
        self.legacy = {}
        self.sources = {}

    def for_provider(self, provider):
        result = dict(self.legacy) if provider in LEGACY_REVIEWED_PROVIDERS else {}
        result.update(self.sources.get(provider, {}))
        return result


def catalog(root=ROOT):
    models = yaml.safe_load((root / "catalog/models.yaml").read_text())["models"]
    ids = {model["id"] for model in models}
    if len(ids) != len(models):
        raise ValueError("Duplicate canonical model IDs")
    aliases = ReviewedAliases()
    for canonical, entry in yaml.safe_load((root / "catalog/aliases.yaml").read_text()).items():
        if canonical not in ids:
            raise ValueError("Alias points to unknown canonical model {}".format(canonical))
        if canonical not in LEGACY_REVIEWED_MODELS and not entry.get("reviewed_sources"):
            raise ValueError("New model identities require explicit reviewed source bindings")
        legacy_aliases = entry.get("legacy_aliases", entry["aliases"] + [canonical])
        if not isinstance(legacy_aliases, list) or any(not isinstance(a, str) or a not in entry["aliases"] + [canonical] for a in legacy_aliases):
            raise ValueError("Legacy aliases must be an exact subset of declared identities")
        for alias in entry["aliases"] + [canonical]:
            if alias in aliases and aliases[alias] != canonical:
                raise ValueError("Ambiguous alias {}".format(alias))
            aliases[alias] = canonical
            if canonical in LEGACY_REVIEWED_MODELS and alias in legacy_aliases:
                aliases.legacy[alias] = canonical
        sources = entry.get("reviewed_sources", {})
        if not isinstance(sources, dict):
            raise ValueError("Reviewed source bindings must be a provider map")
        for provider, source_ids in sources.items():
            if not isinstance(provider, str) or not isinstance(source_ids, list) or not source_ids:
                raise ValueError("Invalid reviewed source binding")
            for source_id in source_ids:
                if not isinstance(source_id, str) or aliases.get(source_id) != canonical:
                    raise ValueError("Reviewed source ID is not an exact declared alias")
                aliases.sources.setdefault(provider, {})[source_id] = canonical
    if ids - set(aliases.values()):
        raise ValueError("Canonical model has no declared identity/source aliases")
    return models, aliases


def normalize(record, aliases, observed_at, source_hash):
    scoped = aliases.for_provider(record["provider"]) if isinstance(aliases, ReviewedAliases) else aliases
    model_id = scoped.get(record["provider_model_id"])
    if model_id is None:
        raise ValueError("Unknown model alias; add it manually before tracking")
    url = urlparse(record["source_url"])
    if url.scheme not in ("https", "http") or not url.hostname:
        raise ValueError("Every observation requires an official source URL")
    quote_unit = record.get("quote_unit", "USD")
    if quote_unit not in ("USD", "EUR", "DBU", "AI_CREDIT"):
        raise ValueError("Unsupported reviewed billing basis")
    if record.get("currency") != (quote_unit if quote_unit in ("USD", "EUR") else None):
        raise ValueError("Currency and reviewed billing basis disagree")
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
    if quote_unit != "USD":
        identity.append(quote_unit)
    # Preserve all existing offering IDs; distinguish new prompt-length bands.
    if minimum or maximum is not None:
        identity.extend([str(minimum), str(maximum)])
    offering_id = record["provider"] + "-" + hashlib.sha256("\0".join(identity).encode()).hexdigest()[:16]
    offering = {key: record.get(key) for key in OFFERING_FIELDS}
    if quote_unit != "USD":
        offering["quote_unit"] = quote_unit
    offering.update(min_input_tokens=minimum, pricing_notes=record.get("pricing_notes", ""))
    offering.update(id=offering_id, model_id=model_id, active=True, last_seen_at=observed_at)
    price = {key: None if record.get(key) is None else round(number(record[key]), 10) for key in PRICE_FIELDS}
    if price["input_per_million"] is None or price["output_per_million"] is None:
        raise ValueError("Input and output prices are required")
    price.update(offering_id=offering_id, observed_at=observed_at, currency=record["currency"], source_url=record["source_url"], source_sha256=source_hash)
    return offering, price


def price_signature(price):
    return tuple(price.get(field) for field in PRICE_FIELDS) + (price["currency"],)
