"""Exact source-bound selections for the current provider coverage expansion."""
import json
import re
from decimal import Decimal

from .common import HTMLTables, markdown_tables, money, number, observation, provider_aliases
from .comparison_expansion import exact_rows
from .public_pricing import require_models, unique_records

REVIEWED_PROVIDERS = frozenset(("arcee", "castform", "cerebras", "perplexity", "upstage"))
NOTES = "Selected text-token API rates only. Tools, storage, training, subscriptions, purchase bonuses and tax are excluded. Unknown cache rates and workload limits are not inferred. "
AGENT_MODELS = "https://docs.perplexity.ai/docs/agent-api/models.md"
CEREBRAS_MODELS = "https://api.cerebras.ai/public/v1/models"
CEREBRAS_UNITS = "https://inference-docs.cerebras.ai/api-reference/models/public-models.md"
UPSTAGE_PRICES = "https://www.upstage.ai/pricing/api"
UPSTAGE_VERSIONS = {
    "solar-pro4-260806": ("https://console.upstage.ai/docs/models/solar-pro-4.md", "solar-pro4"),
    "solar-mini4-260922": ("https://console.upstage.ai/docs/models/solar-mini-4.md", "solar-mini4"),
}


def document(payload, url):
    docs = [d for d in payload.get("documents", []) if d.get("source_url") == url]
    if len(docs) != 1 or not isinstance(docs[0].get("body"), str):
        raise ValueError("Required billing source is missing or repeated: " + url)
    return docs[0]["body"]


def quote(provider, mid, rates, source, notes, **metadata):
    return observation(provider, mid, number(rates[0]), number(rates[1]), source,
        cache_read_per_million=None if len(rates) < 3 or rates[2] is None else number(rates[2]),
        pricing_notes=NOTES + notes, **metadata)


def reviewed_quotes(provider, payload, aliases):
    aliases = provider_aliases(aliases, provider)
    records = []
    if provider == "cerebras":
        units = document(payload, CEREBRAS_UNITS)
        if "Pricing per token in USD." not in units or "Cost per prompt token." not in units:
            raise ValueError("Cerebras default-feed billing units changed")
        for mid, row in exact_rows(payload["catalog"]["data"], "id", aliases).items():
            pricing = row.get("pricing")
            if not isinstance(pricing, dict) or set(pricing) != {"prompt", "completion"}:
                raise ValueError("Cerebras price components require review")
            if row.get("deprecated") is not False or row.get("preview") is not False:
                raise ValueError("Cerebras selected access/lifecycle changed")
            rates = [Decimal(str(pricing[k])) * 1000000 for k in ("prompt", "completion")]
            records.append(quote(provider, mid, rates, CEREBRAS_MODELS,
                "Cerebras Shared Inference advertised default USD/token pricing. Free/paid limits differ; Qwen feed and paid-reference limits disagree, so quote capacities remain unverified. Dedicated inference is separate.",
                region="Shared Inference", quantization=row.get("quantization")))
    elif provider == "castform":
        for mid, row in exact_rows(payload["catalog"]["data"], "model", aliases).items():
            if set(row) != {"model", "input_per_1m_tokens", "output_per_1m_tokens", "currency"} or row["currency"] != "USD":
                raise ValueError("Castform selected inference scope requires review")
            records.append(quote(provider, mid, [row["input_per_1m_tokens"], row["output_per_1m_tokens"]],
                "https://api.castform.com/v1/pricing",
                "Castform advertised inference USD per million tokens, independently of upstream billing. Training is a separate product. No upstream context limit, cache fee, prompt band or serving precision is inferred.", region="advertised inference API"))
    elif provider == "arcee":
        source = "https://docs.arcee.ai/get-started/pricing.md"
        body = document(payload, source)
        if "All prices are in USD." not in body or "Prices per 1M Tokens." not in body:
            raise ValueError("Arcee currency or token denominator changed")
        parser = HTMLTables()
        parser.feed(body)
        header = None
        for cells in parser.rows:
            if cells and cells[0] == "Model Name":
                header = cells
            elif cells and cells[0] in aliases:
                if header != ["Model Name", "Input", "Output", "Cached Input"] or len(cells) != 4:
                    raise ValueError("Arcee selected table headers changed")
                records.append(quote(provider, cells[0], [money(cells[1]), money(cells[2]), money(cells[3])], source,
                    "Arcee Platform USD per million tokens, with exact advertised served IDs. This is an Arcee billing offer, not an inferred direct creator price.", region="Arcee Platform"))
    elif provider == "perplexity":
        from scripts.public_inventory import unquote_tabs
        body = document(payload, AGENT_MODELS)
        if '"currency": "USD"' not in body:
            raise ValueError("Agent API's documented billing currency requires review")
        for headers, cells in markdown_tables(unquote_tabs(body)):
            mid = cells[0].strip("`")
            if mid not in aliases:
                continue
            if headers != ["Model", "Input (\\$/1M)", "Output (\\$/1M)", "Cache read (\\$/1M)", "Service tiers", "Docs"] or cells[4] != "—":
                raise ValueError("Perplexity selected default token scope changed")
            if any(not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value) for value in cells[1:4]):
                raise ValueError("Perplexity selected token rates became conditional")
            records.append(quote(provider, mid, cells[1:4], AGENT_MODELS,
                "Perplexity Agent API default USD per million tokens; the source's response cost identifies USD. Perplexity-hosted IDs identify the serving/billing source, not the model creator. Optional tool fees are separate. Orchestrator private-preview rates and legacy Sonar search/request fees are not substituted.", region="Agent API default"))
    elif provider == "upstage":
        prices = document(payload, UPSTAGE_PRICES)
        marker = re.search(r"window\.__WEBFLOW_CURRENCY_SETTINGS\s*=\s*", prices)
        if not marker:
            raise ValueError("Upstage pricing-page currency witness missing")
        currency, _ = json.JSONDecoder().raw_decode(prices[marker.end():])
        if currency.get("currencyCode") != "USD" or currency.get("symbol") != "$":
            raise ValueError("Upstage published pricing currency changed")
        for mid in aliases:
            if mid not in UPSTAGE_VERSIONS:
                raise ValueError("Unreviewed Upstage served version")
            source, alias = UPSTAGE_VERSIONS[mid]
            body = document(payload, source)
            if "### " + mid + " (Alias: " + alias + ")" not in body:
                raise ValueError("Upstage current version/alias binding changed")
            values = re.findall(r"(?m)^- \*\*Price\*\*: \$([0-9.]+)/1M tokens \((Input Token|Output Token|Cached Token)\)$", body)
            if len(values) != 3 or len({label for _, label in values}) != 3:
                raise ValueError("Upstage selected per-million token fields changed")
            rates = {label: number(value) for value, label in values}
            records.append(quote(provider, mid, [rates[k] for k in ("Input Token", "Output Token", "Cached Token")], source,
                "Upstage current versioned API token quote. The same provider's API pricing page explicitly sets currencyCode USD. Cached-token reads, taxes, prepaid bonus credits and Studio subscriptions stay separate; context shorthand is left unverified.", region="Upstage Console API"))
    else:
        raise ValueError("No comparable quote selection for this provider")
    require_models(records, aliases.keys(), aliases)
    if not records:
        raise ValueError("No explicitly reviewed current-source quotes")
    # Duplicate selected rows are ambiguous even if their amounts are equal.
    if len({(r["provider_model_id"], r["service_tier"], r["region"]) for r in records}) != len(records):
        raise ValueError("Duplicate selected current-source quote")
    return unique_records(records)
