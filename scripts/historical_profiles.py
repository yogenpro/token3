"""Versioned, exact public-source boundaries for historical expansion."""
import json
from pathlib import Path
import re
from functools import lru_cache
from urllib.parse import parse_qsl, parse_qs, urlsplit

CONFIG = Path(__file__).resolve().parents[1] / "config" / "historical_sources.json"
PROFILE = "historical-public-profiles-v1"
DOCUMENT_KINDS = {"archive_index_v2", "archived_native_v2", "public_document_v2"}


@lru_cache(maxsize=1)
def profiles():
    data = json.loads(CONFIG.read_bytes())
    if data.get("schema_version") != 1 or data.get("policy") != PROFILE:
        raise ValueError("Unsupported historical source profiles")
    return data["providers"]


def normalized(url):
    if not isinstance(url, str) or len(url) > 8192 or any(ord(c) < 32 for c in url):
        raise ValueError("Unsafe historical URL")
    p = urlsplit(url)
    benign_anchor = (p.hostname == "docs.together.ai" and p.path.rstrip("/") == "/docs/serverless-models"
                     and re.fullmatch(r"[a-z0-9-]{1,120}", p.fragment or ""))
    if p.scheme not in ("https", "http") or p.username or p.password or (p.fragment and not benign_anchor) or " " in p.path:
        raise ValueError("Unsafe historical URL")
    if p.port not in (None, 443 if p.scheme == "https" else 80):
        raise ValueError("Unsupported historical port")
    # Only scheme/default-port and terminal-slash equivalence, preserving original URLs in records.
    return p.hostname, p.path.rstrip("/"), tuple(sorted(parse_qsl(p.query, keep_blank_values=True)))


def source_spec(url, provider):
    key = normalized(url)
    for spec in profiles().get(provider, {}).get("sources", []):
        if normalized(spec["url"]) == key:
            return spec
    raise ValueError("Historical source is outside the selected public profile")


def archive_query(url, provider):
    p = urlsplit(url)
    q = parse_qs(p.query, keep_blank_values=True)
    if (p.scheme != "https" or p.netloc != "web.archive.org" or p.path != "/cdx/search/cdx" or p.fragment
            or set(q) != {"url", "matchType", "output", "filter", "fl", "limit", "to"}
            or any(len(v) != 1 for v in q.values()) or q["matchType"] != ["exact"] or q["output"] != ["json"]
            or q["filter"] != ["statuscode:200"] or q["fl"] != ["timestamp,original,mimetype,statuscode,digest"]
            or q["limit"] != ["5001"] or not re.fullmatch(r"\d{14}", q["to"][0])):
        raise ValueError("Unsupported historical archive query")
    source_spec(q["url"][0], provider)
    return q["url"][0]
