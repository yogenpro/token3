"""Explicit operating decisions, shared with the static dashboard. Not availability."""
import json
from pathlib import Path

POLICIES = json.loads((Path(__file__).resolve().parent.parent / "config/provider_policies.json").read_text())
if any(set(p) != {"comparisons", "collection", "reason"} or p["comparisons"] != "paused"
       or p["collection"] != "documents_only" or not isinstance(p["reason"], str) or not p["reason"]
       for p in POLICIES.values()):
    raise ValueError("Invalid provider operating policy")


def comparisons_paused(provider):
    return provider in POLICIES
