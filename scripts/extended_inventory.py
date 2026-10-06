"""Adapters for collection-only sources; keep billing rules, not equivalence."""
import re
from decimal import Decimal
from html import escape

from .catalog_inventory import (amount, canonical, digest, entry, money_value,
                                rate, text, _document, _DocumentHTML)

ENVELOPE = "token3.inventory-sources.v1"


def _objects(value, label):
    if not isinstance(value, list) or not value or any(not isinstance(row, dict) for row in value):
        raise ValueError(label + " must be a nonempty object list")
    for row in value:
        if row.get("private") or row.get("is_private") or row.get("is_public") is False or row.get("visibility") == "private":
            raise ValueError("Private model data must not be committed to the public inventory")
    return value


def _model_id(row, key="id"):
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError("Public model catalog lacks a native model ID")
    return value


def _scalar_rates(pricing, units, sentinel=False):
    if not isinstance(pricing, dict):
        raise ValueError("Published model pricing must be an object")
    rates, unknown = [], []
    for key, unit in units.items():
        if key not in pricing or pricing[key] is None:
            continue
        value = pricing[key]
        if sentinel and str(value) == "-1":
            unknown.append(key)
            continue
        if isinstance(value, (dict, list)):
            raise ValueError("Published scalar price changed shape")
        rates.append(rate(key, value, unit))
    return rates, unknown


def _gateway(provider, catalog):
    records = []
    units = {"prompt": "input token", "completion": "output token", "request": "request",
             "input_cache_read": "cached input token", "input_cache_write": "cache-write token",
             "input_cache_write_1h": "cache-write token", "web_search": "search", "internal_reasoning": "reasoning token"}
    if provider == "vercel":
        units = {"input": "input token", "output": "output token", "input_cache_read": "cached input token",
                 "input_cache_write": "cache-write token", "speech_input_character_cost": "input character",
                 "transcription_duration_cost_per_second": "second", "realtime_session_duration_cost_per_second": "second",
                 "realtime_client_message_cost": "message", "audio_input_token_cost": "audio input token",
                 "audio_output_token_cost": "audio output token"}
    for row in _objects(catalog.get("data"), provider + " models"):
        mid = _model_id(row)
        pricing = row.get("pricing")
        rates, unknown = _scalar_rates(pricing, units, sentinel=provider == "openrouter")
        metadata = {key: row[key] for key in ("name", "canonical_slug", "hugging_face_id", "owned_by", "type", "architecture",
                    "context_length", "context_window", "max_tokens", "top_provider", "per_request_limits", "supported_parameters",
                    "supported_specifications", "modalities", "default_parameters", "reasoning_options", "zdr", "no_training",
                    "expiration_date", "knowledge_cutoff") if key in row}
        billing = dict(rules=pricing, currency="USD", state="dynamic_price" if unknown else "reported" if rates else "native_rules_only",
                       unknown_price_dimensions=unknown, source_scope="advertised gateway catalog, not a selected upstream route")
        records.append(entry(provider, mid, "model", row.get("name") or mid, {}, billing, metadata, rates))
    return records


def _huggingface(catalog):
    records = []
    for row in _objects(catalog.get("data"), "Hugging Face chat models"):
        mid = _model_id(row)
        for route in _objects(row.get("providers"), "Hugging Face provider routes"):
            provider = _model_id(route, "provider")
            pricing = route.get("pricing")
            rates = _scalar_rates(pricing, {"input": "1M input tokens", "output": "1M output tokens"})[0] if pricing is not None else []
            # Live latency/throughput measurements are not pricing metadata and
            # must not create change-only history noise.
            metadata = {key: route[key] for key in ("status", "context_length", "is_free", "supports_tools",
                        "supports_structured_output", "is_model_author") if key in route}
            metadata["architecture"] = row.get("architecture")
            records.append(entry("huggingface", mid, "provider_route", mid, {"upstream_provider": provider},
                                 dict(rules=pricing, state="reported" if rates else "source_native_or_unpriced"), metadata, rates))
    return records


def _nebius(catalog):
    records = []
    units = {"input_price_per_million_tokens": "1M input tokens", "output_price_per_million_tokens": "1M output tokens",
             "price_per_image": "image", "price_per_million_tokens": "1M tokens"}
    for model in _objects(catalog, "Nebius public models"):
        for flavor in _objects(model.get("flavors"), "Nebius model flavors"):
            mid = _model_id(flavor, "model_id")
            pricing = {k:v for k,v in flavor.items() if "price" in k or "billing" in k}
            rates = _scalar_rates(pricing, units)[0]
            regions = flavor.get("regions") or [None]
            if not isinstance(regions, list) or any(r is not None and not isinstance(r, dict) for r in regions):
                raise ValueError("Nebius flavor regions changed shape")
            metadata = {k:flavor[k] for k in ("model_type", "model_name", "max_model_len", "context_window_k", "quantization",
                        "external_provider", "tags", "use_cases") if k in flavor}
            metadata.update({k:model[k] for k in ("status", "license", "vendor", "huggingface_url", "size_b") if k in model})
            for region in regions:
                records.append(entry("nebius", mid, "model_flavor", flavor.get("model_name") or mid,
                    {"flavor": flavor.get("label"), "region": region},
                    dict(rules=pricing, state="reported" if rates else "source_native_or_unpriced", currency="USD"), metadata, rates))
    return records


def _ovhcloud(catalog):
    records = []
    for model in _objects(catalog, "OVHcloud catalog"):
        mid = _model_id(model)
        metadata = model.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError("OVHcloud model metadata changed shape")
        usage = metadata.get("usage_information") or {}
        prices = usage.get("pricing")
        if prices is not None and not isinstance(prices, list):
            raise ValueError("OVHcloud price list changed shape")
        native, rates = [], []
        for component in prices or []:
            unit = component.get("price_unit")
            if not isinstance(unit, str) or not unit:
                raise ValueError("OVHcloud published price lacks its native unit")
            value = amount(component.get("price"))
            currency = component.get("currency") or usage.get("currency")
            native.append(dict(amount=value, unit=unit, currency=currency))
            if currency:
                rates.append(rate(unit, value, unit, currency))
        kept = {k:model[k] for k in ("name", "available", "category", "category_v2", "tags") if k in model}
        kept.update({k:metadata[k] for k in ("aliases", "api_base_url", "model_specs", "publishing_information") if k in metadata})
        kept["availability"] = {k:usage[k] for k in ("status", "statuses", "rate_limit") if k in usage}
        records.append(entry("ovhcloud", mid, "model", model.get("name") or mid, {},
            dict(rules=prices, native_rates=native, currency_state="source_provided" if rates else "not_provided",
                 state="native_price_currency_unverified" if native and not rates else "reported" if rates else "source_native_or_unpriced"), kept, rates))
    return records


def _oracle(catalog):
    records = []
    for sku in _objects(catalog.get("items"), "Oracle Generative AI SKUs"):
        mid = _model_id(sku, "partNumber")
        unit = sku.get("metricName")
        if not isinstance(unit, str) or not unit:
            raise ValueError("Oracle SKU lacks its native billing metric")
        found = False
        for localization in _objects(sku.get("currencyCodeLocalizations"), "Oracle currency localizations"):
            if localization.get("currencyCode") != "USD":
                continue
            for price in _objects(localization.get("prices"), "Oracle SKU prices"):
                model = _model_id(price, "model")
                rates = [rate("price", price.get("value"), unit, "USD")]
                records.append(entry("oracle", mid, "sku", sku.get("displayName") or mid, {"price_model": model},
                    dict(rules=price, unit=unit, currency="USD"),
                    {k:sku[k] for k in ("displayName", "serviceCategory") if k in sku}, rates))
                found = True
        if not found:
            raise ValueError("Selected Oracle USD SKU lacks USD pricing")
    return records


def _scaleway(catalog):
    records = []
    for sku in _objects(catalog.get("products"), "Scaleway AI SKUs"):
        mid = _model_id(sku, "sku")
        price = sku.get("price")
        unit = sku.get("unit_of_measure")
        rates = []
        if price is not None:
            money = price.get("retail_price") if isinstance(price, dict) else None
            if not isinstance(money, dict) or not isinstance(unit, dict) or not unit.get("unit"):
                raise ValueError("Scaleway published price lacks structured money or unit")
            rates = [rate("retail_price", money_value(money), unit["unit"], money.get("currency_code"),
                          native_unit_size=unit.get("size"))]
        records.append(entry("scaleway", mid, "sku", sku.get("variant") or sku.get("product") or mid,
            {"locality": sku.get("locality")}, {"rules": price, "unit_of_measure": unit,
                "state": "reported" if rates else "source_native_or_unpriced"},
            {k:sku[k] for k in ("product", "variant", "description", "service_category", "product_category", "properties", "status") if k in sku}, rates))
    return records


class _MixedHTML(_DocumentHTML):
    """Keep MDX Tab titles as source scopes, in addition to HTML headings."""
    def __init__(self):
        super().__init__()
        self.source_tabs = []

    def handle_starttag(self, tag, attrs):
        if tag == "tab":
            self.source_tabs.append(dict(attrs).get("title", "Unnamed source tab"))
        super().handle_starttag(tag, attrs)
        if tag == "table" and self.table is not None:
            self.table["labels"] = list(self.source_tabs) + self.table.get("labels", [])

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if tag == "tab" and self.source_tabs:
            self.source_tabs.pop()


def _mixed_document(body):
    if not re.search(r"<table\b", body, re.I):
        # Inline styling is not pricing identity. Keep its visible content.
        return re.sub(r"</?(?:div|span|strong|em)\b[^>]*>", "", body, flags=re.I)
    lines, table = [], []
    def flush():
        if table:
            lines.append("<table>")
            for row in table:
                cells = [c.strip() for c in row.strip()[1:-1].split("|")]
                if all(re.fullmatch(r":?-+:?", c) for c in cells):
                    continue
                lines.append("<tr>" + "".join("<td>" + c + "</td>" for c in cells) + "</tr>")
            lines.append("</table>")
            table.clear()
    for line in body.splitlines():
        if line.strip().startswith("|") and line.strip().endswith("|"):
            table.append(line)
            continue
        flush()
        heading = re.match(r"^(#{1,6})\s+(.+)", line)
        if heading:
            level = len(heading[1])
            lines.append("<h{0}>{1}</h{0}>".format(level, escape(heading[2])))
        elif line.strip() and not line.lstrip().startswith("<"):
            lines.append("<p>" + line + "</p>")
        else:
            lines.append(line)
    flush()
    return "\n".join(lines)


def _document_identity(cells, headers):
    identities = []
    for index, cell in enumerate(cells):
        if not cell:
            continue
        header = headers[index] if len(cells) == len(headers) else ""
        if re.search(r"price|cost|credit|DBU|input|output|cache", header, re.I) and re.search(r"\d|free|N/?A", cell, re.I):
            continue
        if re.search(r"\$\s*\d|\d\s*(?:€|USD|EUR|CNY)|(?:€|¥)\s*\d", cell, re.I):
            continue
        if re.fullmatch(r"[\d,.\s%-]+", cell):
            continue
        identities.append(cell)
    return identities or ["Unlabeled source row"]


def normalize_extended(provider, payload):
    if payload.get("format") != ENVELOPE:
        raise ValueError("Unrecognized collection-only source envelope")
    adapter = payload.get("adapter")
    records, notes = [], []
    if adapter in ("openrouter", "vercel"):
        if adapter != provider:
            raise ValueError("Gateway adapter/provider mismatch")
        records = _gateway(provider, payload.get("catalog") or {})
    elif adapter == "huggingface": records = _huggingface(payload.get("catalog") or {})
    elif adapter == "nebius": records = _nebius(payload.get("catalog"))
    elif adapter == "ovhcloud": records = _ovhcloud(payload.get("catalog"))
    elif adapter == "oracle": records = _oracle(payload.get("catalog") or {})
    elif adapter == "scaleway": records = _scaleway(payload.get("catalog") or {})
    elif adapter != "documents": raise ValueError("Unknown collection-only catalog adapter")
    if adapter not in ("documents", provider):
        raise ValueError("Catalog adapter/provider identity mismatch")
    documents = payload.get("documents", [])
    if not isinstance(documents, list):
        raise ValueError("Source documents must be a list")
    for document in documents:
        url, body = document.get("source_url"), document.get("body")
        if not isinstance(url, str) or not isinstance(body, str) or not body:
            raise ValueError("Source document lacks its URL/body")
        docs, prose = _document(provider, _mixed_document(body), html_parser=_MixedHTML, identity_builder=_document_identity)
        if not docs:
            raise ValueError("Selected pricing document has no source-native table rows")
        for record in docs:
            record["scope"]["source_url"] = url
            identity = {key:record[key] for key in ("provider", "native_id", "kind", "scope")}
            record["id"] = provider + "-" + digest(identity)[:24]
        records.extend(docs)
        notes.extend(url + ": " + line for line in prose)
    pdf = payload.get("pdf_document")
    if pdf is not None:
        if provider != "snowflake" or not isinstance(pdf, dict):
            raise ValueError("Unexpected PDF extraction source")
        for page in _objects(pdf.get("pages"), "Snowflake extracted pages"):
            if not isinstance(page.get("text"), str) or not page["text"].strip():
                raise ValueError("PDF page lacks extracted billing text")
            records.append(entry(provider, str(page["page"]), "document_page", "Consumption table page " + str(page["page"]),
                {"source_url": pdf.get("source_url"), "page": page["page"]},
                {"text": page["text"], "interpretation": pdf.get("extraction"), "unit": "source-native AI/Platform Credits; no USD conversion"},
                {"table_alignment_verified": False}))
    if payload.get("scope_note"):
        notes.append(payload["scope_note"])
    if payload.get("coverage"):
        notes.append("COVERAGE LIMITATION: " + payload["coverage"])
    return records, sorted(set(notes))
