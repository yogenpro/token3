"""Explicit operating decisions, shared with the static dashboard. Not availability."""
import json
from pathlib import Path

POLICIES = json.loads((Path(__file__).resolve().parent.parent / "config/provider_policies.json").read_text())


def validate_policy(policy):
    if not isinstance(policy, dict) or not isinstance(policy.get("reason"), str) or not policy["reason"].strip():
        raise ValueError("Invalid provider operating policy")
    if set(policy) == {"comparisons", "collection", "reason"}:
        valid = policy["comparisons"] == "paused" and policy["collection"] in ("documents_only", "disabled")
    elif set(policy) == {"excluded_model_ids", "reason"}:
        ids = policy["excluded_model_ids"]
        valid = isinstance(ids, list) and bool(ids) and all(isinstance(mid, str) and mid.strip() == mid and mid for mid in ids)
        valid = valid and len(set(ids)) == len(ids)
    else:
        valid = False
    if not valid:
        raise ValueError("Invalid provider operating policy")


for _policy in POLICIES.values():
    validate_policy(_policy)


def comparisons_paused(provider):
    return POLICIES.get(provider, {}).get("comparisons") == "paused"


def collection_disabled(provider):
    return POLICIES.get(provider, {}).get("collection") == "disabled"


def excluded_model_ids(provider):
    return frozenset(POLICIES.get(provider, {}).get("excluded_model_ids", ()))
