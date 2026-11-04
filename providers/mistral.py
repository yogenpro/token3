"""Selected direct Mistral Standard USD quotes; full document remains native."""
import hashlib
import re

from .common import fetch_text, markdown_tables, money, observation, parse_or_archive, provider_aliases, snapshot
from .public_pricing import require_models

SOURCE = "https://docs.mistral.ai/inference/pricing"
FETCH_URL = SOURCE + ".md"
IDS = ("mistral-large-4", "mistral-small-2603", "ministral-14b-2512", "ministral-8b-2512", "ministral-3b-2512", "codestral-2508")


def parse(body, aliases):
    aliases = provider_aliases(aliases, "mistral")
    records, seen = [], set()
    for headers, cells in markdown_tables(body):
        mid = cells[1].strip("`") if len(cells) > 1 else ""
        if mid not in aliases or mid not in IDS:
            continue
        if headers != ["Model", "API name", "Price"] or mid in seen:
            raise ValueError("Mistral pricing headers or duplicate model changed")
        seen.add(mid)
        rates = {}
        for part in cells[2].split("<br>"):
            match = re.fullmatch(r"(Input|Cached input|Output) (\$[0-9.]+) /M Tokens", part)
            if not match or match[1] in rates:
                raise ValueError("Unsupported Mistral billing expression")
            rates[match[1]] = money(match[2])
        if not {"Input", "Output"} <= rates.keys():
            raise ValueError("Incomplete Mistral token quote")
        records.append(observation("mistral", mid, rates["Input"], rates["Output"], SOURCE,
            cache_read_per_million=rates.get("Cached input"), region="default API routing",
            pricing_notes="Mistral Standard USD per million tokens; the public pricing control establishes USD/Standard. Regional, Batch, Priority, tools and non-token products are excluded. Missing cache prices and endpoint capacities remain unverified."))
    require_models(records, IDS, aliases)
    return snapshot(records, body, SOURCE)


def collect(aliases):
    body = fetch_text(FETCH_URL)
    # Markdown uses dollar symbols; verify the actual published currency/tier
    # controls rather than assigning USD from a locale or an unrelated page.
    controls = fetch_text(SOURCE, headers={"Accept": "text/html"})
    for value in ("USD", "Standard"):
        if not re.search(r'<button\b[^>]*aria-pressed="true"[^>]*>' + value + r'</button>', controls):
            raise ValueError("Mistral default pricing currency/tier requires review")
    result = parse_or_archive(body, SOURCE, parse, aliases)
    result.source_urls = [FETCH_URL, SOURCE]
    result.source_evidence = [dict(source_url=SOURCE, response_sha256=hashlib.sha256(controls.encode()).hexdigest())]
    return result
