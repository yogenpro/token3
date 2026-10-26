"""Explicitly curated token quotes from otherwise source-native collectors.

A source binding is required for every model. Gateway quotes describe the
billing gateway, never an inferred upstream supplier. Unsupported route, fast,
regional, batch and non-token charges remain in the complete native inventory.
"""
from .common import number, observation, provider_aliases
from .public_pricing import require_models, unique_records

from .comparison_expansion import PROVIDERS as EXPANDED_COMPARISON_PROVIDERS

REVIEWED_INVENTORY_PROVIDERS = frozenset(("vercel",)) | EXPANDED_COMPARISON_PROVIDERS
TOKEN_FIELDS = ("input", "output", "input_cache_read", "input_cache_write")


def boundary(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Gateway prompt boundary must be a nonnegative integer")
    return value


def token_bands(pricing):
    """Vercel intervals are explicit half-open integer prompt-token bands."""
    schedules = {}
    for field in TOKEN_FIELDS:
        scalar = pricing.get(field)
        tiers = pricing.get(field + "_tiers")
        if tiers is None:
            schedules[field] = [(0, None, None if scalar is None else number(scalar))]
            continue
        if not isinstance(tiers, list) or not tiers:
            raise ValueError("Gateway token tiers must be a nonempty array")
        rows, previous = [], 0
        for index, tier in enumerate(tiers):
            if not isinstance(tier, dict) or set(tier) - {"min", "max", "cost"}:
                raise ValueError("Unknown gateway token-tier condition")
            # An omitted first lower bound is unbounded below; token counts
            # are nonnegative. Later tiers must supply an explicit lower bound.
            minimum = boundary(tier.get("min", 0 if index == 0 else None))
            maximum = boundary(tier["max"]) if tier.get("max") is not None else None
            if minimum != previous or (maximum is not None and maximum <= minimum):
                raise ValueError("Gateway token tiers overlap or leave a gap")
            if maximum is None and index != len(tiers) - 1:
                raise ValueError("Unbounded gateway token tier is not last")
            rows.append((minimum, maximum, number(tier["cost"])))
            previous = maximum
        if rows[-1][1] is not None or scalar is None or number(scalar) != rows[0][2]:
            raise ValueError("Gateway token tiers are incomplete or disagree with the base rate")
        schedules[field] = rows
    starts = sorted({minimum for rows in schedules.values() for minimum, _, _ in rows})
    result = []
    for index, minimum in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else None
        rates = {}
        for field, rows in schedules.items():
            applicable = [rate for lo, hi, rate in rows if lo <= minimum and (hi is None or minimum < hi)]
            if len(applicable) != 1:
                raise ValueError("Ambiguous gateway token band")
            rates[field] = applicable[0]
        if rates["input"] is None or rates["output"] is None:
            raise ValueError("Missing gateway text-token input/output rate")
        result.append((rates, minimum, end - 1 if end is not None else None))
    return result


def service_bands(pricing):
    long = pricing.get("long_context")
    if long is None:
        return token_bands(pricing)
    if not isinstance(long, dict) or set(long) - {"threshold", *TOKEN_FIELDS}:
        raise ValueError("Unknown gateway service-tier long-context rule")
    threshold = boundary(long["threshold"])
    if threshold == 0 or any(pricing.get(field + "_tiers") is not None for field in TOKEN_FIELDS):
        raise ValueError("Conflicting gateway service-tier band rules")
    short = {key: None if pricing.get(key) is None else number(pricing[key]) for key in TOKEN_FIELDS}
    # Do not inherit missing long-context cache prices from a cheaper band.
    following = {key: None if long.get(key) is None else number(long[key]) for key in TOKEN_FIELDS}
    if any(values[key] is None for values in (short, following) for key in ("input", "output")):
        raise ValueError("Incomplete gateway service-tier long-context rates")
    return [(short, 0, threshold - 1), (following, threshold, None)]


def vercel_quotes(payload, aliases, source):
    rows = payload["catalog"]["data"]
    records = []
    for model in rows:
        model_id = model.get("id")
        if model_id not in aliases:
            continue
        if model.get("type") != "language":
            raise ValueError("Reviewed gateway identity changed modality")
        pricing = model["pricing"]
        if any(value not in (None, "USD") for value in (payload["catalog"].get("currency"), model.get("currency"), pricing.get("currency"))):
            raise ValueError("Gateway quote currency changed from the reviewed USD basis")
        tiers = {"standard": token_bands(pricing)}
        service = pricing.get("service_tiers") or {}
        if not isinstance(service, dict):
            raise ValueError("Gateway service tiers must be an object")
        for tier in ("flex", "priority"):
            if tier in service:
                tiers[tier] = service_bands(service[tier])
        for tier, bands in tiers.items():
            for rates, minimum, maximum in bands:
                records.append(observation("vercel", model_id, rates["input"] * 1000000,
                    rates["output"] * 1000000, source,
                    cache_read_per_million=rates["input_cache_read"] * 1000000 if rates["input_cache_read"] is not None else None,
                    cache_write_per_million=rates["input_cache_write"] * 1000000 if rates["input_cache_write"] is not None else None,
                    context_window=model.get("context_window"), max_output_tokens=model.get("max_tokens"),
                    service_tier=tier, region="default gateway route",
                    min_input_tokens=minimum, max_input_tokens=maximum,
                    pricing_notes="Vercel AI Gateway advertised USD/token prices, not a direct upstream-provider quote or guaranteed route. Explicit integer prompt bands and published Standard/Flex/Priority prices are kept separate. Fast, ultrafast, regional and Batch variants remain native-only. Cache-write TTL is not established by this catalog; writes, tools and non-token fees are excluded from estimates."))
    require_models(records, aliases.keys(), aliases)
    if not records:
        raise ValueError("No explicitly reviewed gateway quotes parsed")
    return unique_records(records)


def reviewed_quotes(provider, payload, aliases, source):
    aliases = provider_aliases(aliases, provider)
    if provider == "vercel":
        return vercel_quotes(payload, aliases, source)
    if provider in EXPANDED_COMPARISON_PROVIDERS:
        from .comparison_expansion import expanded_quotes
        return expanded_quotes(provider, payload, aliases, source)
    raise ValueError("Provider has no separately reviewed native-source adapter")
