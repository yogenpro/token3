"""Read Kimi's public serialized DocTable literals strictly as inert data.

The Markdown export omits these tables. Never evaluate compiled MDX/JavaScript.
Only the witnessed literal table grammar is accepted; drift fails closed.
"""
import re

from .common import fetch_text, money, observation, parse_or_archive, provider_aliases, snapshot
from .public_pricing import require_models

SOURCE = "https://platform.kimi.ai/docs/pricing/chat"
IDS = ("kimi-k3", "kimi-k2.7-code", "kimi-k2.6")
HEADER = ("Model", "Input", "Output", "Cached Input")


def native_notes(body):
    # Preserve public billing/access prose embedded alongside the tables. These
    # are source string literals, never evaluated code or inferred conditions.
    return sorted({literal for literal in re.findall(r'`([^`]*)`', body)
                   if len(literal) >= 30 and '${' not in literal and
                   re.search(r'\b(pric\w*|bill\w*|tokens?|cach\w*|TTL|tax\w*|free|retire\w*)\b', literal, re.I)})


def tables(body):
    if "1 MTok = 1,000,000 tokens. All prices above are per MTok consumed." not in body:
        raise ValueError("Kimi pricing token denominator changed")
    matches = list(re.finditer(r"columns:\[(.*?)\],rows:\[(.*?)\]\]\}\)", body, re.S))
    if len(matches) != 2:
        raise ValueError("Incomplete Kimi serialized pricing tables")
    result = []
    for index, match in enumerate(matches):
        columns = match[1]
        # Tooltip titles are explicit children; widths and explanatory tips are
        # presentation, never additional price components.
        headers = re.findall(r'(?:title|children):`(Model|Input|Output|Cached Input|5m writes|1h writes)`', columns)
        expected = list(HEADER) + (["5m writes", "1h writes"] if index == 0 else [])
        if headers != expected:
            raise ValueError("Kimi pricing column order changed")
        rows = []
        for raw in (match[2] + "]").split("],["):
            raw = raw.removeprefix("[").removesuffix("]")
            row = re.fullmatch(r'_jsx\(_components\.a,\{href:`(/guide/[a-z0-9-]+)`,children:`([a-z0-9.\-]+)`\}\),(.+)', raw)
            if not row:
                raise ValueError("Unsupported Kimi serialized model row")
            prices = row[3].split(",")
            if len(prices) != len(expected) - 1 or any(not re.fullmatch(r'`\$[0-9.]+ / MTok`', p) for p in prices):
                raise ValueError("Incomplete Kimi token prices")
            rows.append((row[2], [p.strip("`") for p in prices]))
        if len(rows) != 3 or len({mid for mid, _ in rows}) != len(rows):
            raise ValueError("Duplicate or incomplete Kimi model table")
        result.append((expected, rows))
    return result


def parse(body, aliases):
    aliases = provider_aliases(aliases, "moonshot")
    for condition in (
        "All K3 series models support a 1,048,576-token context window.",
        "All K2 series models support a 262,144-token context window.",
        "starting October 31, 2026, K2 series models will no longer be available to newly registered users; existing users are not affected.",
        "We plan to retire all K2 series models by the end of December 2026",
    ):
        if condition not in body:
            raise ValueError("Kimi reviewed capacity/access scope changed")
    records = []
    for headers, rows in tables(body):
        for mid, prices in rows:
            if mid not in aliases or mid not in IDS:
                continue
            rates = [money(p.removesuffix(" / MTok")) for p in prices]
            records.append(observation("moonshot", mid, rates[0], rates[1], SOURCE,
                cache_read_per_million=rates[2], cache_write_per_million=rates[3] if len(rates) == 5 else None,
                context_window=1048576 if mid == "kimi-k3" else 262144, region="international API",
                pricing_notes="Kimi direct API Standard USD per million tokens. K3 cache writes use the default 5-minute TTL; 1-hour writes, Highspeed and Batch remain separate. K2 models are unavailable to new users from October 31, 2026; existing users are unaffected, with retirement planned by the end of December 2026. Cache writes, tools, tax and account top-ups are excluded from estimates."))
    require_models(records, IDS, aliases)
    return snapshot(records, body, SOURCE)


def collect(aliases):
    result = parse_or_archive(fetch_text(SOURCE, headers={"Accept": "text/html"}), SOURCE, parse, aliases)
    result.source_urls = [SOURCE]
    return result
