"""Read-only API diagnostics: field shapes/counts and reviewed public prices only.

Never save authenticated response bodies or print account/private model details.
"""
import json
import os
from collections import Counter

from providers import fireworks
from providers.common import safe_error
from .normalize import catalog


MODES = {"default", "standard", "priority", "fast", "spot"}


def shape(value, depth=2):
    if isinstance(value, dict) and depth:
        return {key: shape(v, depth-1) for key, v in sorted(value.items())}
    if isinstance(value, list) and depth:
        shapes = {json.dumps(shape(v, depth-1), sort_keys=True) for v in value}
        return {"list_items": [json.loads(s) for s in sorted(shapes)[:10]], "count": len(value)}
    return type(value).__name__


def report(payload, aliases):
    models = payload["data"]
    counts = Counter("missing" if "pricing" not in row else type(row["pricing"]).__name__ for row in models)
    modes = Counter(row.get("serverless_mode") if row.get("serverless_mode") in MODES else "unrecognized_or_missing" for row in models)
    price_fields = {}
    samples = []
    for row in models:
        mid = row.get("id") or row.get("name")
        reviewed = isinstance(mid, str) and mid in aliases and mid.startswith("accounts/fireworks/models/")
        private = row.get("private") or row.get("is_private") or row.get("is_public") is False or row.get("visibility") == "private"
        for key, value in row.items():
            if any(word in key.lower() for word in ("pric", "sku", "serverless", "mode")):
                details = shape(value) if reviewed and not private else type(value).__name__
                price_fields.setdefault(key, set()).add(json.dumps(details, sort_keys=True))
        if not reviewed or private:
            continue
        sample = dict(public_model_id=mid, mode=row.get("serverless_mode") if row.get("serverless_mode") in MODES else "unrecognized_or_missing",
                      fields=sorted(row), pricing_shape=shape(row.get("pricing")))
        if isinstance(row.get("pricing"), list):
            sample["published_skus"] = []
            for sku in row["pricing"]:
                if not isinstance(sku, dict):
                    continue
                money = sku.get("amount")
                if isinstance(money, dict):
                    money = {key: money[key] for key in ("currencyCode", "units", "nanos") if key in money}
                sample["published_skus"].append(dict(sku=sku.get("sku"), unit=sku.get("unit"), amount=money))
        samples.append(sample)
    return dict(model_rows=len(models), pricing_shapes=dict(counts), serving_modes=dict(modes),
                model_fields=sorted({key for row in models for key in row}),
                pricing_related_field_shapes={k: [json.loads(s) for s in sorted(v)[:10]] for k,v in sorted(price_fields.items())},
                reviewed_public_model_samples=samples[:12])


def main():
    key = os.environ.get("FIREWORKS_API_KEY", "").strip()
    if not key:
        raise ValueError("FIREWORKS_API_KEY is required for this diagnostic")
    _, aliases = catalog()
    result = fireworks.collect(aliases)
    if key in (result.source_payload or ""):
        raise ValueError("Source unexpectedly contains a configured credential; refusing to print diagnostics")
    print("Source kind:", result.source_kind)
    print("Fallback:", safe_error(result.fallback_reason, [key]) if result.fallback_reason else "none")
    print("Curated parser:", safe_error(result.parse_error, [key]) if result.parse_error else "ok")
    if result.source_kind != "api":
        raise ValueError("Authenticated API request did not produce a catalog")
    output = report(json.loads(result.source_payload), aliases)
    output["source_page_count"] = len(result.source_urls or [])
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
