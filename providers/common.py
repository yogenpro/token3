import hashlib
import json
import re
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


@dataclass
class Collection:
    records: List[Dict[str, Any]]
    source_url: str
    source_sha256: str
    authoritative_catalog: bool = False
    source_payload: Optional[str] = None
    parse_error: Optional[str] = None
    source_urls: Optional[List[str]] = None
    source_kind: Optional[str] = None
    fallback_reason: Optional[str] = None


class _NoCredentialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Authenticated APIs must not forward a credential to a redirected host.
        return None


def safe_error(error, secrets=()):
    message = "{}: {}".format(type(error).__name__, error)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[redacted]")
            if secret.lower().startswith("bearer "):
                message = message.replace(secret[7:], "[redacted]")
    return message[:500]


def fetch_text(url: str, headers=None) -> str:
    if headers and urlparse(url).scheme != "https":
        raise ValueError("Authenticated sources require HTTPS")
    request_headers = {"User-Agent": "TokenTokenToken/0.1 (public pricing observation)", "Accept": "application/json, text/markdown, text/html"}
    request_headers.update(headers or {})
    open_url = build_opener(_NoCredentialRedirect()).open if headers else urlopen
    error = None
    for attempt in range(3):
        try:
            request = Request(url, headers=request_headers)
            with open_url(request, timeout=30) as response:
                body = response.read(8 * 1024 * 1024 + 1)
                if len(body) > 8 * 1024 * 1024:
                    raise ValueError("Source exceeds the 8 MiB response limit")
                return body.decode("utf-8")
        except Exception as exc:
            error = exc
            if isinstance(exc, HTTPError) and exc.code < 500 and exc.code != 429:
                break
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError("Could not fetch {}: {}".format(url, safe_error(error, (headers or {}).values())))


def snapshot(records, body, source_url, authoritative=False, source_kind=None):
    if not records:
        raise ValueError("No tracked, publicly priced models parsed; refusing an empty snapshot")
    return Collection(records, source_url, hashlib.sha256(body.encode("utf-8")).hexdigest(), authoritative, body,
                      source_kind=source_kind)


def parse_or_archive(body, source_url, parser, *args, **kwargs):
    """Retain successfully fetched source data even when curated parsing fails."""
    try:
        return parser(body, *args, **kwargs)
    except Exception as exc:
        return Collection([], source_url, hashlib.sha256(body.encode("utf-8")).hexdigest(), False, body,
                          "{}: {}".format(type(exc).__name__, exc)[:500], [source_url])


def number(value) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError("Missing or invalid numeric price")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid numeric price: {}".format(value))
    if not result.is_finite() or result < 0:
        raise ValueError("Prices must be finite and non-negative")
    return float(result)


def money(cell: str, optional=False) -> Optional[float]:
    cell = cell.replace("\\$", "$").strip()
    if optional and cell in ("-", "—", "N/A", ""):
        return None
    match = re.fullmatch(r"\$([0-9]+(?:\.[0-9]+)?)", cell)
    if not match:
        raise ValueError("Unrecognized USD price cell: {}".format(cell))
    return number(match.group(1))


def observation(provider, model_id, input_price, output_price, source_url, **metadata):
    return dict(provider=provider, provider_model_id=model_id,
                input_per_million=input_price, output_per_million=output_price,
                cache_read_per_million=metadata.pop("cache_read_per_million", None),
                cache_write_per_million=metadata.pop("cache_write_per_million", None),
                currency="USD", source_url=source_url,
                context_window=metadata.pop("context_window", None),
                min_input_tokens=metadata.pop("min_input_tokens", 0),
                max_input_tokens=metadata.pop("max_input_tokens", None),
                max_output_tokens=metadata.pop("max_output_tokens", None),
                pricing_notes=metadata.pop("pricing_notes", ""),
                quantization=metadata.pop("quantization", None),
                service_tier=metadata.pop("service_tier", "standard"),
                region=metadata.pop("region", "unspecified"),
                variant=metadata.pop("variant", "standard"), **metadata)


def markdown_tables(text):
    header = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line[1:-1].split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        if header is None:
            header = cells
        elif len(cells) == len(header):
            yield header, cells


class HTMLTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
