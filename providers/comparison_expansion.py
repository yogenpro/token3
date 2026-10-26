"""Separately reviewed billing interpretations; never promote native records.

Every enrolled source ID needs an exact catalog binding. Prices come only from
the fetched source. Unsupported modalities, billing rules and routes fail closed.
"""
import re
from decimal import Decimal
from html.parser import HTMLParser

from .common import markdown_tables, money, number, observation
from .deepseek_pricing import Tables, expand, parse_models
from .public_pricing import require_models, section

PROVIDERS = frozenset(("openrouter", "alibaba", "huggingface", "snowflake", "cloudflare",
                       "databricks", "oracle", "nebius", "xai", "zai", "ovhcloud", "scaleway", "minimax", "deepseek"))
NOTES = "Selected text-token list rates. Tools, storage, cache writes, subscriptions, account fees, tax and negotiated discounts are excluded from workload estimates. "


def quote(provider, mid, rates, source, unit="USD", **metadata):
    result = observation(provider, mid, number(rates[0]), number(rates[1]), source,
        cache_read_per_million=None if len(rates) < 3 or rates[2] is None else number(rates[2]),
        pricing_notes=NOTES + metadata.pop("pricing_notes", ""), **metadata)
    if unit != "USD":
        result.update(quote_unit=unit, currency=unit if unit == "EUR" else None)
    return result


def exact_rows(rows, key, aliases):
    selected = {}
    for row in rows:
        mid = row.get(key)
        if mid in aliases:
            if mid in selected:
                raise ValueError("Duplicate reviewed source ID: " + mid)
            selected[mid] = row
    if set(selected) != set(aliases):
        raise ValueError("Incomplete reviewed source IDs: " + ", ".join(sorted(set(aliases) - set(selected))))
    return selected


def api_quotes(provider, payload, aliases, source):
    records = []
    catalog = payload["catalog"]
    if isinstance(catalog,dict) and catalog.get('currency') not in (None,'USD'):
        raise ValueError("Reviewed API catalog currency changed")
    if provider == "openrouter":
        for mid, row in exact_rows(catalog["data"], "id", aliases).items():
            pricing = row["pricing"]
            if row.get('currency') not in (None,'USD'):
                raise ValueError("Reviewed OpenRouter currency changed")
            if set(pricing) - {"prompt", "completion", "input_cache_read", "input_cache_write"}:
                raise ValueError("Unreviewed gateway price component")
            if row["architecture"]["output_modalities"] != ["text"]:
                raise ValueError("Reviewed gateway output modality changed")
            rates = [number(pricing[k]) * 1000000 for k in ("prompt", "completion")]
            rates.append(None if pricing.get("input_cache_read") is None else number(pricing["input_cache_read"]) * 1000000)
            records.append(quote(provider, mid, rates, source,
                region="advertised default gateway route", context_window=row.get("context_length"),
                max_output_tokens=(row.get("top_provider") or {}).get("max_completion_tokens"),
                pricing_notes="OpenRouter advertised USD/token gateway prices; no selected supplier or guaranteed route. Credit-purchase fees are additional. Dynamic/router and conditional rates are excluded."))
    elif provider == "huggingface":
        for mid, row in exact_rows(catalog["data"], "id", aliases).items():
            if row.get('architecture', {}).get('output_modalities') != ['text'] or 'text' not in row.get('architecture', {}).get('input_modalities', []):
                raise ValueError("Reviewed Hugging Face text modality changed")
            # One explicitly selected routed supplier per model, rather than
            # silently choosing the cheapest available supplier on each run.
            routes = [p for p in row["providers"] if p["provider"] == "novita"]
            if len(routes) != 1 or routes[0].get("status") != "live":
                raise ValueError("Reviewed Hugging Face Novita route missing or unavailable")
            route = routes[0]
            if set(route["pricing"]) != {"input", "output"}:
                raise ValueError("Unsupported Hugging Face route pricing")
            records.append(quote(provider, mid, [route["pricing"][k] for k in ("input", "output")], source,
                context_window=route.get("context_length"), region="Hugging Face routed via novita",
                pricing_notes="Hugging Face routed Novita billing, USD per million tokens; not a direct Novita quote or automatic route. Included credits are excluded."))
    elif provider == "nebius":
        if any(row.get('status') != 'active' for row in catalog if any(f.get('model_id') in aliases for f in row['flavors'])):
            raise ValueError("Reviewed Nebius model is not active")
        rows = [flavor for row in catalog for flavor in row["flavors"]]
        for mid, row in exact_rows(rows, "model_id", aliases).items():
            if row["label"] != "cheap" or row.get("external_provider") is not False:
                raise ValueError("Nebius reviewed flavor changed")
            rates = [row[k] for k in ("input_price_per_million_tokens", "output_price_per_million_tokens")]
            rates.append(row.get("input_cached_price_per_million_tokens"))
            regions = row["regions"]
            reviewed_regions = {
                "deepseek-ai/DeepSeek-V4-Pro-0813": {"uk-south1"},
                "openai/gpt-oss-120b": {"eu-north1"},
                "Qwen/Qwen3.8-27B": {"us-central1"},
                "zai-org/GLM-5.3": {"us-north1"},
                "zai-org/GLM-5.3-Flash": {"us-north1"},
            }
            if not regions or len({r['name'] for r in regions}) != len(regions):
                raise ValueError("Invalid Nebius regions")
            if {r['name'] for r in regions} != reviewed_regions[mid]:
                raise ValueError("Nebius region scope requires new review")
            for region in regions:
                records.append(quote(provider, mid, rates, source, context_window=row.get("max_model_len"),
                    quantization=row.get("quantization"), variant="cheap", region=region["name"],
                    pricing_notes="Nebius public cheap flavor, USD per million tokens; exact flavor/region/precision preserved."))
    return records


def document(payload):
    if len(payload.get("documents", [])) != 1:
        raise ValueError("Expected exactly one reviewed pricing document")
    return payload["documents"][0]["body"]


def document_quotes(provider, payload, aliases, source):
    body = document(payload)
    records = []
    if provider == "cloudflare":
        rows = markdown_tables(section(body, "LLM model pricing"))
        selected = []
        for headers, cells in rows:
            if cells[0] not in aliases:
                continue
            if headers != ["Model", "Price in Tokens", "Price in Neurons"]:
                raise ValueError("Cloudflare reviewed headers changed")
            rates = {}
            for part in re.split(r"\s*<br\s*/?>\s*", cells[1]):
                match = re.fullmatch(r"\$([0-9.]+) per M (input|output|cached input) tokens", part)
                if not match or match[2] in rates:
                    raise ValueError("Unreviewed Cloudflare token expression")
                rates[match[2]] = number(match[1])
            if not {"input", "output"} <= rates.keys():
                raise ValueError("Incomplete Cloudflare token rates")
            selected.append(cells[0])
            records.append(quote(provider, cells[0], [rates["input"], rates["output"], rates.get("cached input")], source,
                quantization="fp8" if "-fp8" in cells[0] else None,
                variant="fast" if cells[0] == "@cf/meta/llama-3.3-70b-instruct-fp8-fast" else "standard",
                pricing_notes="Published Price in Tokens column, not an inferred neuron conversion. Paid-plan requirements and free allowances are outside estimates."))
        if len(selected) != len(set(selected)):
            raise ValueError("Duplicate Cloudflare quote")
    elif provider == "zai":
        if "All prices are in USD" not in body or "Prices per 1M tokens." not in body:
            raise ValueError("Z.ai denominator/currency missing")
        for headers, cells in markdown_tables(section(body, "Models")):
            if cells[0] not in aliases:
                continue
            if headers != ["Model", "Input", "Cached Input", "Cached Input Storage", "Output"]:
                raise ValueError("Z.ai reviewed token headers changed")
            records.append(quote(provider, cells[0], [money(cells[1]), money(cells[4]), money(cells[2])], source,
                region="international API", pricing_notes="International Z.ai API, USD per million tokens. Cached-input storage promotions are separate; Coding Plan and Chinese Zhipu billing excluded."))
    elif provider == "xai":
        for headers, cells in markdown_tables(section(body, "Text API Pricing", level=3)):
            m = re.fullmatch(r"(grok-4\.7) \((<|≥) 200k prompt tokens\)", cells[0])
            if not m or m[1] not in aliases:
                continue
            if headers != ["Model", "Context", "Input / 1M tokens", "Cached input / 1M tokens", "Output / 1M tokens"]:
                raise ValueError("xAI token headers changed")
            records.append(quote(provider, m[1], [money(cells[2]), money(cells[4]), money(cells[3])], source,
                min_input_tokens=0 if m[2] == "<" else 200000, max_input_tokens=199999 if m[2] == "<" else None,
                pricing_notes="xAI Standard text pricing, full prompt boundary <200,000 / ≥200,000. Regional, Batch and Priority modifiers excluded. Source context shorthand left unverified."))
        if len(records) != 2 or {r['min_input_tokens'] for r in records} != {0, 200000}:
            raise ValueError("Incomplete xAI prompt schedule")
    elif provider == "minimax":
        llm = section(body, "LLM")
        headers_expected = ["**Model**", "**Input** \\$ / M tokens", "**Output** \\$ / M tokens", "**Prompt caching Read** \\$ / M tokens"]
        for tier, start, stop in (("standard", "**Standard**", "**Priority**"), ("priority", "**Priority**", "\\* Priority provides")):
            if llm.count(start) != 1 or stop not in llm:
                raise ValueError("MiniMax tier boundary changed")
            block = llm.split(start, 1)[1].split(stop, 1)[0]
            for headers, cells in markdown_tables(block):
                m = re.fullmatch(r"\*\*(MiniMax-M3)\*\* (≤|>) 512k input tokens(?:\\\*)? Permanent 50% off", cells[0])
                if not m or m[1] not in aliases:
                    continue
                if headers != headers_expected:
                    raise ValueError("MiniMax token headers changed")
                rates = []
                for cell in cells[1:]:
                    mprice = re.fullmatch(r"~~\\\$([0-9.]+)~~ \\\$([0-9.]+)", cell)
                    if not mprice or Decimal(mprice[1]) != Decimal(mprice[2]) * 2:
                        raise ValueError("Unreviewed MiniMax discount expression")
                    rates.append(number(mprice[2]))
                records.append(quote(provider, m[1], rates, source, service_tier=tier,
                    min_input_tokens=0 if m[2] == "≤" else 512001, max_input_tokens=512000 if m[2] == "≤" else None,
                    region="international API", pricing_notes="Published permanent 50% discount, Standard/Priority and full-prompt ≤512,000/>512,000 schedules kept separate; no subscription pricing."))
        if len(records) != 4 or {(r['service_tier'],r['min_input_tokens']) for r in records} != {(t,b) for t in ('standard','priority') for b in (0,512001)}:
            raise ValueError("Incomplete MiniMax tier/prompt schedule")
    elif provider == "deepseek":
        versions = {"deepseek-flash": "DeepSeek-V4.1-Flash-1017", "deepseek-v4-pro": "DeepSeek-V4-Pro-0813"}
        expected_schedule = "Peak hours are 01:00 - 04:00 and 06:00 - 10:00 UTC, Monday through Friday, excluding Chinese public holidays. All other hours are off-peak, including weekends and Chinese public holidays in full."
        for row in parse_models(body):
            mid = row['native_id']
            if mid not in aliases:
                continue
            if row['version'] != versions[mid] or row['schedule'] != expected_schedule:
                raise ValueError("DeepSeek served version or billing schedule requires new review")
            for period in ('PEAK','OFF-PEAK'):
                rates = {r['dimension']:r['amount'] for r in row['rates'] if r['conditions']['time_of_use']==period}
                records.append(quote(provider, mid, [rates[k] for k in ('input','output','cache_read')], source,
                    region=period.lower() + " UTC schedule", variant=period.lower(),
                    pricing_notes="Explicit " + period + " scenario; not inferred current applicability. " + expected_schedule + " Served version " + row['version'] + ". Capacity shorthand remains unverified."))
    return records


def databricks_quotes(payload, aliases, source):
    body = next(d['body'] for d in payload['documents'] if d['source_url'] == source)
    parser = Tables()
    parser.feed(body)
    candidates = [expand(t) for t in parser.tables if t and t[0][0][0] == 'Model' and 'Pay Per Token (DBU Per 1M Tokens)' in [c[0] for c in t[0]]]
    if len(candidates) != 1:
        raise ValueError("Missing unique Databricks Standard token table")
    rows = candidates[0]
    if rows[1] != ['Model','Input','Output','Cache read'] or rows[0] != ['Model'] + ['Pay Per Token (DBU Per 1M Tokens)'] * 3:
        raise ValueError("Databricks merged billing columns changed")
    records = []
    for mid, row in exact_rows([dict(id=r[0], cells=r) for r in rows[2:]], 'id', aliases).items():
        cells = row['cells']
        if len(cells) != 4:
            raise ValueError("Incomplete Databricks token row")
        records.append(quote('databricks', mid, [number(cells[1]),number(cells[2]),None if cells[3]=='-' else number(cells[3])], source, unit="DBU",
            region="native DBU schedule", pricing_notes="DBU per million tokens; no USD-per-DBU assumption. A monetary bill depends on cloud, region and account SKU price. Provisioned/hourly and Batch excluded."))
    return records


def snowflake_quotes(payload, aliases, source):
    pdf = payload.get('pdf_document') or {}
    all_text = '\n'.join(p['text'] for p in pdf.get('pages', []))
    if not re.search(r'\b5\s+This feature is available as a Preview, subject to the Preview Terms', all_text):
        raise ValueError("Snowflake model footnote 5 requires new review")
    pages = [p['text'] for p in pdf.get('pages',[]) if re.search(r'^\s*Table 6\(b\): Snowflake AI Features Table, Cortex Inference with Prompt Caching\s*$',p['text'],re.M)]
    if not pages or len(pages) > 3:
        raise ValueError("Snowflake complete aligned Table 6(b) unavailable")
    text = '\n'.join(p.split('Table 6(b):',1)[1].split('Table 6(c):',1)[0] for p in pages)
    if not re.search(r'AI Credits per one million Tokens',text) or not re.search(r'Input\s+Output\s+Cache Write\s+Cache Read',text):
        raise ValueError("Snowflake credit unit/columns changed")
    records = []
    for mid in aliases:
        # The superscript 5 footnote is attached to selected model names in
        # PDF layout extraction. It is explicitly matched, never stripped from
        # arbitrary IDs. Other footnotes or long-context suffixes fail review.
        matches = re.findall(r'^\s*' + re.escape(mid) + r'5\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+|-)\s+([0-9.]+)\s*$',text,re.M)
        if len(matches) != 1:
            raise ValueError("Missing or ambiguous Snowflake reviewed model row: " + mid)
        inp,out,write,read = matches[0]
        records.append(quote('snowflake',mid,[inp,out,read],pdf['source_url'],unit='AI_CREDIT',
            region="native AI Credit schedule", variant="preview", pricing_notes="Table 6(b), AI Credits per million tokens; distinct from Platform Credits. Footnote 5 marks these models Preview, subject to Snowflake Preview Terms; account/region access is unverified. USD cost depends on global/regional routing and contract discounts. Cache-write amount " + write + " AI Credits/1M is excluded from estimates; retention is unverified."))
    return records


ORACLE_PAIRS = {
    'B112004': ('B112004','B112005','OCI Generative AI - OpenAI - gpt-oss-120b'),
    'B112006': ('B112006','B112007','OCI Generative AI - OpenAI - gpt-oss-20b'),
}


def oracle_quotes(payload, aliases, source):
    rows = payload['catalog']['items']
    records=[]
    for mid in aliases:
        inp,out,prefix=ORACLE_PAIRS[mid]
        rates=[]
        for sku,direction in ((inp,'Input'),(out,'Output')):
            matches=[r for r in rows if r['partNumber']==sku]
            if len(matches)!=1:
                raise ValueError("Missing/duplicate Oracle reviewed SKU")
            row=matches[0]
            if row['displayName'] != prefix + ' - ' + direction + ' Tokens' or row['metricName']!='1,000,000 Tokens':
                raise ValueError("Oracle SKU meaning or unit changed")
            localizations=row['currencyCodeLocalizations']
            if len(localizations)!=1 or localizations[0]['currencyCode']!='USD':
                raise ValueError("Oracle reviewed currency changed")
            prices=localizations[0]['prices']
            if len(prices)!=1 or prices[0]['model']!='PAY_AS_YOU_GO':
                raise ValueError("Oracle price-model changed")
            rates.append(prices[0]['value'])
        records.append(quote('oracle',mid,rates,source,region="public USD PAY_AS_YOU_GO catalog",
            pricing_notes="Explicit paired input/output SKUs " + inp + "/" + out + ", USD per 1,000,000 tokens. Deployment availability and limits are unverified."))
    return records


def scaleway_quotes(payload, aliases, source):
    records=[]
    rows=payload['catalog']['products']
    for mid in aliases:
        selected=[r for r in rows if r['product']==mid and r.get('properties',{}).get('generative_apis',{}).get('consumption_mode')=='realtime' and r.get('locality',{}).get('region')=='fr-par']
        rates={}
        for row in selected:
            kind=row['properties']['generative_apis']['token_type']
            if kind not in ('input_token','output_token'):
                raise ValueError("Unreviewed Scaleway token component")
            if kind in rates or row['product_category']!='Generative APIs' or row['status']!='general_availability' or row['unit_of_measure']!={'size':1000,'unit':'token'}:
                raise ValueError("Scaleway SKU scope changed")
            price=row['price']['retail_price']
            if price['currency_code']!='EUR' or isinstance(price['units'],bool) or not isinstance(price['units'],int) or not isinstance(price['nanos'],int) or not 0<=price['nanos']<1000000000:
                raise ValueError("Invalid Scaleway EUR money")
            rates[kind]=float((Decimal(price['units'])+Decimal(price['nanos'])/1000000000)*1000)
        if set(rates)!={'input_token','output_token'}:
            raise ValueError("Incomplete Scaleway realtime pair")
        records.append(quote('scaleway',mid,[rates['input_token'],rates['output_token']],source,unit='EUR',region='fr-par',
            pricing_notes="EUR retail price per 1,000 tokens ×1,000. Realtime fr-par only; no FX conversion, Batch or dedicated nodes."))
    return records


class PriceCards(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cards=[]
        self.card=None

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='a' and '/public-cloud/ai-endpoints/catalog/' in attrs.get('href','') and attrs.get('aria-label'):
            if self.card is not None:
                raise ValueError("Nested OVH price card")
            self.card=[attrs['href'],[]]
        if self.card is not None and tag=='br':
            self.card[1].append(' ')

    def handle_data(self,data):
        if self.card is not None:
            self.card[1].append(data)

    def handle_endtag(self,tag):
        if tag=='a' and self.card is not None:
            self.cards.append((self.card[0], ' '.join(self.card[1])))
            self.card=None


def ovhcloud_quotes(payload, aliases, source):
    page=payload['reviewed_price_cards']
    if page['source_url'] != 'https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/':
        raise ValueError("Unreviewed OVHcloud price-card source")
    parser=PriceCards();parser.feed(page['body'])
    records=[]
    for mid in aliases:
        suffix='/catalog/'+mid+'/'
        matches=[text for href,text in parser.cards if href.endswith(suffix)]
        if len(matches)!=1:
            raise ValueError("Missing/duplicate OVHcloud reviewed EUR price card")
        text=matches[0]
        amounts=re.findall(r'([0-9]+(?:\.[0-9]+)?)\s*€\s*/\s*Mtoken\s*\(\s*(input|output)\s*\)',text)
        rates=dict((k,number(v)) for v,k in amounts)
        if len(amounts)!=2 or set(rates)!={'input','output'}:
            raise ValueError("OVHcloud explicit EUR/token price card changed")
        records.append(quote('ovhcloud',mid,[rates['input'],rates['output']],page['source_url'],unit='EUR',region='public EUR price cards',
            pricing_notes="Explicit EUR per million token website price cards. API catalog currency remains unverified and is not inferred from these prices. No FX conversion."))
    return records


def expanded_quotes(provider,payload,aliases,source):
    if not aliases:
        raise ValueError("Provider requires explicit reviewed source bindings")
    if provider in ('openrouter','huggingface','nebius'):
        records=api_quotes(provider,payload,aliases,source)
    elif provider in ('cloudflare','zai','xai','minimax','deepseek'):
        records=document_quotes(provider,payload,aliases,source)
    elif provider=='databricks':records=databricks_quotes(payload,aliases,source)
    elif provider=='snowflake':records=snowflake_quotes(payload,aliases,source)
    elif provider=='oracle':records=oracle_quotes(payload,aliases,source)
    elif provider=='scaleway':records=scaleway_quotes(payload,aliases,source)
    elif provider=='ovhcloud':records=ovhcloud_quotes(payload,aliases,source)
    elif provider=='alibaba':
        # Limit initial review to the flat, explicitly USD Singapore GLM row.
        records=[]
        body=document(payload)
        candidates=[]
        for block in re.findall(r'<Tab title="Singapore">(.*?)</Tab>',body,re.S):
            if not re.search(r'>\s*glm-5\.3\s*<',block):
                continue
            parser=Tables();parser.feed(block)
            for table in parser.tables:
                rows=expand(table)
                if any(row and row[0] in aliases for row in rows[1:]):
                    candidates.append(rows)
        if len(candidates)!=1:
            raise ValueError("Alibaba reviewed Singapore table missing/duplicated")
        rows=candidates[0]
        expected=['Model ID','Deployment scope','Mode','Input tokens per request','Input price (per 1 million tokens)','Output price (per 1 million tokens) > Chain of thought and answer']
        if rows[0][:6]!=expected or len(rows[0])!=7 or not rows[0][6].startswith('Free quota'):
            raise ValueError("Alibaba reviewed token headers changed")
        for mid,row in exact_rows([dict(id=r[0],cells=r) for r in rows[1:]],'id',aliases).items():
            cells=row['cells']
            if len(cells)!=7 or cells[1:4]!=['International','Non-Thinking and Thinking modes','flat-rate pricing']:
                raise ValueError("Alibaba deployment/mode/prompt scope changed")
            records.append(quote(provider,mid,[money(cells[4].replace('\\\\$','$')),money(cells[5].replace('\\\\$','$'))],source,
                region='Singapore / International',pricing_notes="Model Studio Singapore International flat-rate USD/1M schedule for Non-Thinking and Thinking modes. Other regions, free quotas and caching discounts excluded."))
    else:raise ValueError("Unsupported comparison source")
    require_models(records,aliases,aliases)
    identities=[(r['provider_model_id'],r['service_tier'],r['region'],r['min_input_tokens'],r['max_input_tokens']) for r in records]
    if len(identities)!=len(set(identities)):
        raise ValueError("Duplicate reviewed quote scope")
    return records
