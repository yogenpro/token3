import hashlib
from .normalize import PRICE_FIELDS


def event(kind, offering, observed_at, field=None, old=None, new=None):
    identity = "|".join(map(str, (kind, offering["id"], observed_at, field, old, new)))
    pct = None
    if kind == "price_changed" and old not in (None, 0) and new is not None:
        pct = round((new - old) / old * 100, 4)
    return dict(id=hashlib.sha256(identity.encode()).hexdigest()[:24], kind=kind,
                offering_id=offering["id"], model_id=offering["model_id"], provider=offering["provider"],
                observed_at=observed_at, field=field, old=old, new=new, change_pct=pct)


def detect_changes(old_offering, offering, previous, current, observed_at):
    events = []
    if old_offering is None:
        # Discovery is NOT evidence of the provider's actual launch date.
        events.append(event("offering_added", offering, observed_at))
    elif not old_offering["active"]:
        events.append(event("offering_restored", offering, observed_at))
    else:
        for field in ("context_window", "quantization", "variant", "max_output_tokens"):
            if old_offering.get(field) != offering.get(field):
                events.append(event("offering_updated", offering, observed_at, field, old_offering.get(field), offering.get(field)))
    if previous is not None:
        for field in PRICE_FIELDS:
            if previous.get(field) != current.get(field):
                events.append(event("price_changed", offering, observed_at, field, previous.get(field), current.get(field)))
    return events
