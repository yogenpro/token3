"""Meta Model API Standard mode; Contributor and subscriptions stay separate."""
import re

from .common import fetch_text, markdown_tables, money, observation, parse_or_archive, provider_aliases, snapshot
from .public_pricing import require_models, section

SOURCE = "https://dev.meta.ai/docs/pricing-rate-limits"
FETCH_URL = SOURCE + ".md"
GROUPS = {"Muse Wonder": ("muse-wonder-1.0",), "Muse Spark": ("muse-spark-1.3", "muse-spark-1.2", "muse-spark-1.1")}


def parse(body, aliases):
    aliases = provider_aliases(aliases, "meta")
    records = []
    for title, ids in GROUPS.items():
        block = section(section(body, "Model pricing"), title, 3)
        if not all("`" + mid + "`" in block for mid in ids):
            raise ValueError("Meta model group identity changed")
        if title == "Muse Spark" and "`muse-spark-1.3`, `muse-spark-1.2`, and `muse-spark-1.1` in Standard mode" not in block:
            raise ValueError("Meta Standard model binding changed")
        if "No long-context premium" not in body:
            raise ValueError("Meta prompt pricing scope changed")
        rates = {}
        for header, cells in markdown_tables(block):
            expected = {"Usage", "Standard mode (per 1M tokens)", "Contributor mode (per 1M tokens)"}
            if len(header) != len(expected) or set(header) != expected:
                raise ValueError("Meta billing mode or denominator changed")
            usage = cells[header.index("Usage")]
            if usage not in ("Input", "Output", "Cached input") or usage in rates:
                raise ValueError("Meta duplicate or unknown token component")
            rates[usage] = money(cells[header.index("Standard mode (per 1M tokens)")])
        if set(rates) != {"Input", "Output", "Cached input"}:
            raise ValueError("Incomplete Meta pricing group")
        for mid in ids:
            if mid not in aliases:
                continue
            records.append(observation("meta", mid, rates["Input"], rates["Output"], SOURCE,
                cache_read_per_million=rates["Cached input"], region="Meta Model API",
                pricing_notes="Meta Model API Standard mode, USD per million tokens, without a long-context premium. Contributor-mode training permission/discounts and Muse Code subscriptions are separate. Web-search grounding and other tools are excluded; endpoint capacities remain unverified."))
    require_models(records, [mid for ids in GROUPS.values() for mid in ids], aliases)
    return snapshot(records, body, SOURCE)


def collect(aliases):
    result = parse_or_archive(fetch_text(FETCH_URL), SOURCE, parse, aliases)
    result.source_urls = [FETCH_URL]
    return result
