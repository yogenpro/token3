"""Full source-native pricing inventory, independent of curated dashboard aliases.

Normalizes storage/identity, not economic equivalence: native units, formulas,
unknown prices and table scopes stay explicit. Nothing here estimates costs.
"""
import hashlib
import json
import re
from decimal import Decimal
from html import unescape

from providers.public_pricing import PricingHTML
from .provider_inventory import _payload_format


PARSER_VERSION = 1


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value):
    return " ".join(unescape(str(value)).replace("\\$", "$").split())


def amount(value):
    if value is None or isinstance(value, bool):
        raise ValueError("Missing monetary amount")
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid monetary amount")
    return format(result.normalize(), "f")


def rate(label, value, unit, currency="USD", **conditions):
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("Invalid or missing native currency")
    if unit is not None and (not isinstance(unit, str) or not unit):
        raise ValueError("Invalid native billing unit")
    return dict(dimension=label, amount=amount(value), currency=currency, unit=unit, conditions=conditions)


def money_value(value):
    units_raw, nanos_raw = value.get("units", "0"), value.get("nanos", 0)
    if isinstance(units_raw, bool) or isinstance(nanos_raw, bool):
        raise ValueError("Invalid structured monetary amount")
    units, nanos = Decimal(str(units_raw)), Decimal(str(nanos_raw))
    if not units.is_finite() or not nanos.is_finite() or units != units.to_integral_value() or nanos != nanos.to_integral_value():
        raise ValueError("Structured monetary fields must be finite integers")
    if units < 0 or not 0 <= nanos < 1000000000:
        raise ValueError("Structured monetary amount is outside valid bounds")
    return units + nanos / 1000000000


def entry(provider, native_id, kind, label, scope, billing, metadata=None, rates=None):
    identity = dict(provider=provider, native_id=str(native_id), kind=kind, scope=scope)
    return dict(id=provider + "-" + digest(identity)[:24], provider=provider, native_id=str(native_id), kind=kind,
                label=label, scope=scope, billing=billing, rates=rates or [], metadata=metadata or {},
                comparison_eligible=False)


def _models(provider, payload):
    models = payload if isinstance(payload, list) else payload.get("data")
    if not isinstance(models, list) or not models:
        raise ValueError("Full model catalog must contain a nonempty model list")
    records = []
    for model in models:
        if not isinstance(model, dict):
            raise ValueError("Model catalog contains a non-object item")
        mid = model.get("model_name") if provider == "deepinfra" else model.get("id")
        if not isinstance(mid, str) or not mid:
            raise ValueError("Model catalog is missing a native model ID")
        if model.get("private") or model.get("is_private") or model.get("is_public") is False or model.get("visibility") == "private":
            raise ValueError("Private model data must not be committed to the public inventory")
        pricing = model.get("pricing")
        rates = []
        if provider == "deepinfra":
            if not isinstance(pricing, dict) or not pricing.get("type"):
                raise ValueError("DeepInfra model lacks its pricing type")
            units = {"cents_per_input_token": "input token", "cents_per_output_token": "output token",
                     "cents_per_input_sec": "input second", "cents_per_output_sec": "output second",
                     "cents_per_sec": "compute second", "cents_per_input_chars": "input character",
                     "cents_per_image_unit": "provider image unit", "cents_per_frame_unit": "provider frame unit"}
            for key, unit in units.items():
                if pricing.get(key) is not None:
                    rates.append(rate(key, Decimal(str(pricing[key])) / 100, unit, native_currency_unit="cent"))
            if pricing.get("default_price_cents") is not None:
                rates.append(rate("default_price_cents", Decimal(str(pricing["default_price_cents"])) / 100, None,
                                  native_currency_unit="cent", default_example=True, unit_verified=False))
            # Multipliers, image/frame sizing, tables, discounts and prose are
            # retained verbatim in billing rules, not guessed into flat rates.
        elif provider == "novita":
            if pricing is not None and not isinstance(pricing, dict):
                raise ValueError("Novita pricing must be an object")
            def append_novita_rates(prices, prefix="", **conditions):
                for key, value in (prices or {}).items():
                    if isinstance(value, dict) and value.get("price_per_m_decimal") is not None:
                        rates.append(rate(prefix + key, value["price_per_m_decimal"], "1M tokens",
                                          source_field="price_per_m_decimal", **conditions))
            append_novita_rates(pricing)
            tiers = model.get("tiered_billing_configs") or []
            if not isinstance(tiers, list):
                raise ValueError("Novita tiered billing configuration is not a list")
            for tier_index, tier in enumerate(tiers):
                append_novita_rates(tier.get("pricing"), "tier_" + str(tier_index) + ".",
                                    source_tier_bounds={k:v for k,v in tier.items() if k != "pricing"})
            # Integer-only and multimodal billing values are explicitly native
            # billing units, NEVER converted to dollars or treated as free.
            pricing = dict(rules=pricing, native_input_billing_units=model.get("input_token_price_per_m"),
                           native_output_billing_units=model.get("output_token_price_per_m"),
                           tiered_billing=model.get("is_tiered_billing"), tiered_billing_configs=tiers)
        elif provider == "together":
            if not isinstance(pricing, dict) or not pricing:
                raise ValueError("Together API model has incomplete pricing")
            if model.get("type") in ("chat", "language") and not all(key in pricing for key in ("input", "output")):
                raise ValueError("Together text model lacks input/output prices")
            for key in ("input", "output", "cached_input", "hourly", "base", "finetune"):
                if pricing.get(key) is None:
                    continue
                unit = "1M tokens" if model.get("type") in ("chat", "language") and key in ("input", "output", "cached_input") else None
                rates.append(rate(key, pricing[key], unit, source_field=key, unit_verified=unit is not None))
            # Other modality/base/hourly/training components are decimal
            # amounts, but not assigned text units absent reviewed semantics.
        elif provider == "fireworks":
            # The complete serverless catalog includes routing/unpriced
            # products with no SKU list. Preserve them as unknown, not free.
            if pricing is not None and not isinstance(pricing, list):
                raise ValueError("Fireworks published pricing must be a SKU list")
            if isinstance(pricing, list):
                pricing = sorted(pricing, key=canonical)
            for sku in pricing or []:
                value = sku.get("amount")
                currency = "USD"
                if isinstance(value, dict):
                    currency = value.get("currencyCode")
                    value = money_value(value)
                if not sku.get("unit") or not currency:
                    raise ValueError("Fireworks price must specify its native unit/currency")
                rates.append(rate(sku["sku"], value, sku["unit"], currency))
        keys = ("type", "model_type", "input_modalities", "output_modalities", "max_tokens", "context_size",
                "context_length", "max_output_tokens", "quantization", "status", "features", "endpoints", "usage_identifier")
        metadata = {key: model[key] for key in keys if key in model}
        if provider == "fireworks":
            metadata.update({key:model[key] for key in ("kind", "pricing_mode", "service_tier", "aliases", "use_cases") if key in model})
        scope = {"serving_mode": model.get("serverless_mode")} if provider == "fireworks" else {}
        billing = dict(state="reported" if rates else "source_native_or_unpriced", rules=pricing)
        records.append(entry(provider, mid, "model", model.get("display_name") or model.get("title") or mid,
                             scope, billing, metadata, rates))
    return records


def _azure(payload):
    records = []
    if not isinstance(payload.get("Items"), list) or not payload["Items"]:
        raise ValueError("Azure retail catalog is empty")
    for item in payload["Items"]:
        if not item.get("meterId") or not item.get("unitOfMeasure") or not item.get("currencyCode"):
            raise ValueError("Azure meter lacks its ID, unit or currency")
        scope = {key: item.get(key) for key in ("skuId", "armRegionName", "type", "tierMinimumUnits", "effectiveStartDate")}
        metadata = {key: item.get(key) for key in ("meterName", "skuName", "productName", "armSkuName", "location", "isPrimaryMeterRegion")}
        prices = [rate("retailPrice", item["retailPrice"], item["unitOfMeasure"], item["currencyCode"])]
        rules = {key: item[key] for key in ("retailPrice", "unitPrice", "unitOfMeasure", "currencyCode", "reservationTerm", "savingsPlan") if key in item}
        records.append(entry("azure", item["meterId"], "meter", item["meterName"], scope, rules, metadata, prices))
    return records


def _bedrock(payload):
    records = []
    for feed, catalog in payload.items():
        if not isinstance(catalog, dict) or "products" not in catalog:
            continue
        for term_type, skus in catalog["terms"].items():
            for sku, offers in skus.items():
                product = catalog["products"].get(sku)
                if product is None:
                    raise ValueError("AWS pricing term has no matching product")
                for offer_id, offer in offers.items():
                    for code, dimension in offer["priceDimensions"].items():
                        if not dimension.get("unit") or not dimension.get("pricePerUnit"):
                            raise ValueError("AWS price dimension lacks currency/unit")
                        scope = dict(feed=feed, term_type=term_type, offer_id=offer_id, begin_range=dimension.get("beginRange"),
                                     end_range=dimension.get("endRange"), effective_date=offer.get("effectiveDate"))
                        billing = dict(unit=dimension["unit"], prices=dimension["pricePerUnit"], applies_to=dimension.get("appliesTo"),
                                       term_attributes=offer.get("termAttributes", {}), description=dimension.get("description"))
                        rates = [rate("pricePerUnit", value, dimension["unit"], currency) for currency, value in dimension["pricePerUnit"].items()]
                        records.append(entry("bedrock", code, "sku_dimension", product.get("attributes", {}).get("model") or
                                             product.get("attributes", {}).get("servicename") or sku, scope, billing, product, rates))
    return records


def _google(payload):
    data = payload["cloud_billing_catalog"]
    records = []
    for sku in data["catalog"]["skus"]:
        if not sku.get("name"):
            raise ValueError("Google billing SKU lacks its resource name")
        rates = []
        for info in sku.get("pricingInfo", []):
            expression = info.get("pricingExpression", {})
            for tier in expression.get("tieredRates", []):
                money = tier["unitPrice"]
                if not money.get("currencyCode") or not expression.get("usageUnit"):
                    raise ValueError("Google SKU rate lacks native currency/unit")
                value = money_value(money)
                rates.append(rate("tieredRate", value, expression["usageUnit"], money["currencyCode"],
                                  start_usage_amount=tier.get("startUsageAmount"), effective_time=info.get("effectiveTime"),
                                  display_quantity=expression.get("displayQuantity"), base_unit=expression.get("baseUnit"),
                                  base_unit_conversion=expression.get("baseUnitConversionFactor")))
        records.append(entry("vertex", sku["name"], "sku", sku.get("description", sku["name"]),
                             dict(service=data["service"]["name"], regions=sorted(sku.get("serviceRegions", []))),
                             dict(pricing_info=sku.get("pricingInfo", []), geo_taxonomy=sku.get("geoTaxonomy")),
                             dict(category=sku.get("category"), service_provider=sku.get("serviceProviderName")), rates))
    return records


class _DocumentHTML(PricingHTML):
    """Keep headings/tab scopes and pricing prose; discard scripts/navigation."""
    def __init__(self):
        super().__init__()
        self.heading = None
        self.headings = []
        self.heading_levels = {}
        self.blocks = []
        self.paragraphs = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self.skip += 1
        if not self.skip:
            if re.fullmatch(r"h[1-6]", tag): self.heading = []
            if tag in ("p", "li"): self.blocks.append((tag, []))
        super().handle_starttag(tag, attrs)
        if tag == "table" and self.table is not None:
            self.table["heading_scope"] = list(self.headings[-6:])

    def handle_data(self, data):
        if not self.skip:
            if self.heading is not None: self.heading.append(data)
            for _, values in self.blocks:
                values.append(data)
        super().handle_data(data)

    def handle_endtag(self, tag):
        if re.fullmatch(r"h[1-6]", tag) and self.heading is not None:
            level = int(tag[1])
            self.heading_levels = {k:v for k,v in self.heading_levels.items() if k < level}
            self.heading_levels[level] = text(" ".join(self.heading))
            self.headings = [self.heading_levels[k] for k in sorted(self.heading_levels)]
            self.heading = None
        if tag in ("p", "li"):
            for i in range(len(self.blocks)-1, -1, -1):
                if self.blocks[i][0] == tag:
                    self.paragraphs.append(text(" ".join(self.blocks[i][1])))
                    del self.blocks[i:]
                    break
        if tag in ("script", "style", "nav", "footer", "header") and self.skip:
            self.skip -= 1
        super().handle_endtag(tag)


def _markdown(body):
    headings, tables, notes, rows, scope = [], [], [], [], []
    heading_levels = {}
    def flush():
        nonlocal rows
        if rows:
            tables.append(dict(rows=rows, labels=[], heading_scope=scope))
        rows = []
    for raw in body.splitlines():
        line = raw.strip()
        heading = re.match(r"^(#{1,6})\s+(.+)", line)
        if heading:
            flush()
            level = len(heading[1])
            heading_levels = {k:v for k,v in heading_levels.items() if k < level}
            heading_levels[level] = text(heading[2])
            headings = [heading_levels[k] for k in sorted(heading_levels)]
        elif line.startswith("|") and line.endswith("|"):
            cells = [text(cell) for cell in line[1:-1].split("|")]
            if all(re.fullmatch(r":?-+:?", cell) for cell in cells): continue
            if not rows: scope = list(headings)
            rows.append(cells)
        else:
            flush()
            if line and not line.startswith("[!"): notes.append(text(line))
    flush()
    return tables, notes


def _quoted_rates(cells, headers, provider, headings):
    """Expose every dollar amount, without inventing unit/condition mappings."""
    result = []
    for column, cell in enumerate(cells):
        label = headers[column] if len(headers) == len(cells) else "source_cell_{}".format(column)
        matches = list(re.finditer(r"\$\s*(\d[\d,]*(?:\.\d+)?)", cell))
        for component, match in enumerate(matches):
            end = matches[component+1].start() if component+1 < len(matches) else len(cell)
            # A cell can quote several rates with different units. Never apply
            # the first component's unit to every amount in that cell.
            basis = cell[match.end():end] + " " + label
            if len(matches) == 1:
                basis = cell + " " + label
            unit_match = re.search(r"(?:/|\bper\s+)(?:\s*)(?:1[MKmk]|1,000,000|1,000|million)?\s*(?:MTok|tokens?(?:\s+per\s+hour)?|characters?|minutes?|hours?|seconds?|images?|megapixels?|requests?|calls?|searches?|GB(?:-day|-month)?)\b", basis, re.I)
            unit = text(unit_match[0]) if unit_match else None
            # Only explicitly named OpenAI token-tier tables use this basis.
            if unit is None and provider == "openai" and any(re.fullmatch(r"(?:Standard|Batch|Flex|Fast|Ultrafast) pricing data", h) for h in headings):
                unit = "1M tokens"
            result.append(rate(label + ":" + str(component), match[1].replace(",", ""), unit,
                               source_expression=cell, unit_verified=unit is not None, active_rate_not_inferred=True))
    return result


def _document(provider, body):
    format_, _, _ = _payload_format(body)
    if format_ == "html":
        parser = _DocumentHTML()
        parser.feed(body)
        tables, paragraphs = parser.tables, parser.paragraphs
    else:
        tables, paragraphs = _markdown(body)
    records = []
    for index, table in enumerate(tables):
        rows = table["rows"]
        if not rows: continue
        headers = rows[0]
        # Source-native columns and scope are preserved even where official
        # prose/merged cells prevent assigning one numerical rate and unit.
        scope = dict(table=index, headings=table.get("heading_scope", []), tabs=table.get("labels", []), headers=headers)
        for position, cells in enumerate(rows[1:]):
            if not any(cells): continue
            identities = [cell for cell in cells if cell and not re.search(r"\$\s*\d", cell)]
            key = digest(dict(identity=identities))[:24]
            billing = dict(cells=cells, columns=headers, alignment_verified=len(cells) == len(headers),
                           interpretation="source-native expressions; no inferred unit or cross-provider equivalence")
            metadata = {}
            if len(headers) == len(cells):
                source_fields = dict(zip(headers, cells))
                for field in ("API model string", "Model string for API", "MODEL ID"):
                    if source_fields.get(field):
                        value = source_fields[field].strip("`")
                        link = re.search(r"\]\(/docs/model/([^)]+)\)", value)
                        metadata["source_model_id"] = link[1] if link else value
                        break
            records.append(entry(provider, key, "document_row", identities[0] if identities else "Pricing row",
                                 scope, billing, metadata, _quoted_rates(cells, headers, provider, scope["headings"])))
    notes = sorted(set(p for p in paragraphs if re.search(r"\$\s*\d|\b(pric\w*|charg\w*|bill\w*|discount\w*|cache|tokens?|per|free|through|starting|effective)\b", p, re.I)))
    return records, notes


def normalize_inventory(provider, body, source_kind):
    format_, payload, _ = _payload_format(body)
    notes = []
    if format_ == "json":
        if provider in ("deepinfra", "novita", "together", "fireworks"):
            records = _models(provider, payload)
        elif provider == "azure": records = _azure(payload)
        elif provider == "bedrock": records = _bedrock(payload)
        elif provider == "vertex" and "cloud_billing_catalog" in payload:
            records = _google(payload)
            document = payload.get("curated_pricing_document", {}).get("body")
            if document:
                docs, notes = _document(provider, document)
                records += docs
        else:
            raise ValueError("Unknown full-catalog JSON schema for " + provider)
    else:
        records, notes = _document(provider, body)
    if not records:
        raise ValueError("Full inventory is empty; previous catalog retained")
    unique = {}
    for record in records:
        if record["id"] in unique and unique[record["id"]] != record:
            # Some documents have several unlabeled rows for the same product.
            # Preserve each as a source-local occurrence, never guess a tier.
            record = dict(record, id=record["id"] + "-" + str(sum(k.startswith(record["id"]) for k in unique)))
        unique[record["id"]] = record
    result = dict(schema_version=1, parser_version=PARSER_VERSION, provider=provider, source_kind=source_kind,
                  records=sorted(unique.values(), key=lambda r:r["id"]), billing_notes=notes)
    # No collection timestamps, raw HTML scripts, JSON object-key ordering or
    # model-list ordering enter this semantic hash.
    return result, digest(result)
