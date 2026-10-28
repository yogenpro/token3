"""Conservative, reproducible historical extraction; no network or quote promotion."""
import base64
import gzip
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

MAX_BYTES = 16 * 1024 * 1024
EXTRACTOR = "historical-native-v1"
SERVICES = ("AmazonBedrock", "AmazonBedrockFoundationModels")
KINDS = {"aws_version_index", "aws_price_list", "archive_index", "deepinfra_api", "deepinfra_html"}


def timestamp(value):
    if not isinstance(value, str) or len(value) > 50:
        raise ValueError("Invalid historical timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid historical timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("Historical timestamp needs a timezone")
    return parsed


def archive_time(stamp):
    if not isinstance(stamp, str) or not re.fullmatch(r"\d{14}", stamp):
        raise ValueError("Invalid archive timestamp")
    return datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()


def public_source(url, provider):
    """Intentionally narrow: these adapters cannot import arbitrary/authenticated URLs."""
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) < 33 for c in url):
        raise ValueError("Unsafe historical source URL")
    p = urlsplit(url)
    if p.scheme not in ("https", "http") or p.username or p.password or p.fragment or p.port:
        raise ValueError("Unsafe historical source URL")
    if provider == "bedrock":
        pattern = r"/offers/v1\.0/aws/(AmazonBedrock|AmazonBedrockFoundationModels)/(?:index\.json|\d{14}/us-east-1/index\.json)"
        valid = p.scheme == "https" and p.netloc == "pricing.us-east-1.amazonaws.com" and re.fullmatch(pattern, p.path) and not p.query
    elif provider == "deepinfra":
        valid = not p.query and ((p.netloc == "api.deepinfra.com" and p.path == "/models/list")
                                or (p.netloc == "deepinfra.com" and p.path in ("/pricing", "/pricing/", "/models", "/models/")))
    else:
        valid = False
    if not valid:
        raise ValueError("Unsupported historical public source")


def validate_capture(capture):
    if capture.get("source_kind") in ("archive_index_v2", "archived_native_v2", "public_document_v2", "arquivo_index_v3", "arquivo_native_v3", "commoncrawl_index_v4", "commoncrawl_native_v4"):
        from .historical_expansion import validate_capture as validate_v2
        return validate_v2(capture)
    kind, provider = capture["source_kind"], capture["provider"]
    if kind not in KINDS or provider != ("bedrock" if kind.startswith("aws_") else "deepinfra"):
        raise ValueError("Unsupported historical source adapter")
    timestamp(capture["retrieved_at"])
    for field in ("archive_capture_at", "source_published_at"):
        if capture[field] is not None:
            if timestamp(capture[field]) > timestamp(capture["retrieved_at"]):
                raise ValueError("Historical source time follows retrieval")
    source = capture["source_url"]
    if kind == "archive_index":
        p = urlsplit(source)
        allowed = {"url", "matchType", "output", "filter", "fl", "limit", "to"}
        query = parse_qs(p.query, keep_blank_values=True)
        if (p.scheme != "https" or p.netloc != "web.archive.org" or p.path != "/cdx/search/cdx"
                or p.fragment or set(query) != allowed or any(len(v) != 1 for v in query.values())
                or query["matchType"] != ["exact"] or query["output"] != ["json"]
                or query["filter"] != ["statuscode:200"]
                or query["fl"] != ["timestamp,original,mimetype,statuscode,digest"]
                or query["limit"] != ["5001"] or not re.fullmatch(r"\d{14}", query["to"][0])):
            raise ValueError("Unsupported historical archive query")
        public_source(query["url"][0], "deepinfra")
        if capture["request_scope"] != {"target_url": query["url"][0]}:
            raise ValueError("Archive query scope differs")
    else:
        public_source(source, provider)
    replay = capture["replay_url"]
    archived = kind in ("deepinfra_api", "deepinfra_html")
    if archived:
        if set(capture["request_scope"]) != {"index_capture_id"}:
            raise ValueError("Unsupported archive request scope")
        stamp = timestamp(capture["archive_capture_at"]).astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
        if replay != "https://web.archive.org/web/{}id_/{}".format(stamp, source):
            raise ValueError("Archive replay target differs")
        if not isinstance(capture["archive_digest"], str) or not re.fullmatch(r"[A-Z2-7]{32}", capture["archive_digest"]):
            raise ValueError("Missing archive content digest")
        if capture["source_published_at"] is not None:
            raise ValueError("Archive capture is not publication")
    elif replay is not None or capture["archive_capture_at"] is not None or capture["archive_digest"] is not None:
        raise ValueError("Unexpected archive metadata")


def validate_discovery_failure(row):
    """Operator-reported failed lookup, with date precision and no invented body/capture."""
    keys = {"kind", "id", "capture_id", "provider", "source_url", "checked_date", "recorded_at",
            "state", "http_status", "provenance", "comparison_eligible"}
    if (set(row) != keys or row["capture_id"] is not None or row["provider"] != "deepinfra"
            or row["state"] != "request_failed" or row["provenance"] != "operator_reported_discovery_check"
            or row["comparison_eligible"] is not False):
        raise ValueError("Invalid historical discovery failure")
    if not isinstance(row["checked_date"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["checked_date"]):
        raise ValueError("Discovery check needs its actual date")
    day = datetime.strptime(row["checked_date"], "%Y-%m-%d").date()
    if day > timestamp(row["recorded_at"]).date():
        raise ValueError("Discovery check follows its recording date")
    status = row["http_status"]
    if status is not None and (type(status) is not int or not 400 <= status <= 599):
        raise ValueError("Discovery failure cannot assert success")
    if not isinstance(row["source_url"], str) or len(row["source_url"]) > 4096 or any(ord(c) < 33 for c in row["source_url"]):
        raise ValueError("Unsafe discovery URL")
    p = urlsplit(row["source_url"])
    q = parse_qs(p.query, keep_blank_values=True)
    if (p.scheme != "https" or p.netloc != "web.archive.org" or p.path != "/cdx/search/cdx" or p.fragment
            or set(q) != {"url", "matchType", "output", "filter", "fl", "limit", "to"}
            or any(len(v) != 1 for v in q.values()) or q["matchType"][0] not in ("exact", "prefix")
            or q["output"] != ["json"] or q["filter"] != ["statuscode:200"]
            or q["fl"] != ["timestamp,original,mimetype,statuscode,digest"] or q["limit"] != ["5001"]
            or not re.fullmatch(r"\d{8}(?:\d{6})?", q["to"][0])):
        raise ValueError("Unsupported discovery lookup")
    target = q["url"][0]
    public_source("https://" + target if "://" not in target else target, "deepinfra")


def decoded(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("Historical source exceeds byte cap")
    if raw.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as handle:
            result = handle.read(MAX_BYTES + 1)
        if len(result) > MAX_BYTES:
            raise ValueError("Decoded historical source exceeds byte cap")
        return result
    return raw


def _pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("Duplicate historical JSON key")
        result[k] = v
    return result


def json_source(raw):
    def invalid(_):
        raise ValueError("Nonfinite historical JSON number")
    return json.loads(decoded(raw), parse_float=str, object_pairs_hook=_pairs, parse_constant=invalid)


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.table, self.row, self.cell, self.skip = [], None, None, None, 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if self.skip:
            return
        if tag == "table":
            if self.table is not None:
                raise ValueError("Nested historical table")
            self.table = []
        if tag == "tr" and self.table is not None:
            if self.row is not None:
                raise ValueError("Incomplete historical table row")
            self.row = []
        if tag in ("th", "td") and self.row is not None:
            if self.cell is not None:
                raise ValueError("Incomplete historical cell")
            self.cell = {"text": [], "links": []}
        if tag == "a" and self.cell is not None and dict(attrs).get("href"):
            self.cell["links"].append(dict(attrs)["href"])

    def handle_data(self, data):
        if not self.skip and self.cell is not None and data.strip():
            self.cell["text"].append(data.strip())

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if self.skip:
            return
        if tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = " ".join(self.cell["text"])
            self.row.append(self.cell)
            self.cell = None
        if tag == "tr" and self.row is not None:
            if self.cell is not None:
                raise ValueError("Incomplete historical cell")
            self.table.append(self.row)
            self.row = None
        if tag == "table" and self.table is not None:
            if self.row is not None:
                raise ValueError("Incomplete historical table row")
            self.tables.append(self.table)
            self.table = None


def extract(capture, raw, context):
    """Return assertion payloads and coverage, reproducible from retained bytes only."""
    if capture.get("source_kind") in ("archive_index_v2", "archived_native_v2", "public_document_v2", "arquivo_index_v3", "arquivo_native_v3", "commoncrawl_index_v4", "commoncrawl_native_v4"):
        from .historical_expansion import extract as extract_v2
        return extract_v2(capture, raw, context)
    validate_capture(capture)
    kind = capture["source_kind"]
    if capture["archive_digest"] is not None:
        digest = base64.b32encode(hashlib.sha1(raw).digest()).decode()
        if digest != capture["archive_digest"]:
            raise ValueError("Archive source digest differs")
        index = context.get(capture["request_scope"].get("index_capture_id"))
        if index is None or index[0]["source_kind"] != "archive_index":
            raise ValueError("Missing retained archive index")
        query = parse_qs(urlsplit(index[0]["source_url"]).query)
        if query["url"][0].rstrip("/") != capture["source_url"].rstrip("/"):
            raise ValueError("Archive index belongs to a different source")
        stamp = timestamp(capture["archive_capture_at"]).astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
        if not any(row[0] == stamp and row[1] == capture["source_url"] and row[3] == "200" and row[4] == digest
                   for row in json_source(index[1])[1:]):
            raise ValueError("Archive capture lacks an exact retained index witness")
    assertions = []

    def emit(native_id, assertion_type, pointer, value, scope, effective=None):
        if effective is not None:
            timestamp(effective)
        assertions.append(dict(kind="assertion", provider=capture["provider"], capture_id=capture["id"],
            extractor=EXTRACTOR, assertion_type=assertion_type, native_id=native_id, identity_scope=scope,
            source_pointer=pointer, source_record=value, source_reported_effective_at=effective,
            review_status="unreviewed_historical", comparison_eligible=False))

    if kind == "archive_index":
        data = json_source(raw)
        header = ["timestamp", "original", "mimetype", "statuscode", "digest"]
        if not isinstance(data, list) or (data and data[0] != header):
            raise ValueError("Invalid archive index header")
        for row in data[1:]:
            if not isinstance(row, list) or len(row) != 5 or row[3] != "200" or not re.fullmatch(r"[A-Z2-7]{32}", row[4]):
                raise ValueError("Invalid archive index row")
            archive_time(row[0])
            public_source(row[1], "deepinfra")
            if row[1].rstrip("/") != capture["request_scope"]["target_url"].rstrip("/"):
                raise ValueError("Archive index URL normalization requires review")
        coverage = dict(state="index_only", returned_entries=max(0, len(data) - 1), entry_cap=5001,
                        cap_reached=len(data) - 1 >= 5001, scope="one exact URL; replay completeness not implied")
    elif kind.startswith("aws_"):
        data = json_source(raw)
        scope = capture["request_scope"]
        service = scope["service"]
        if service not in SERVICES or data.get("offerCode") != service or data.get("publicationDate") != capture["source_published_at"]:
            raise ValueError("AWS service/publication differs")
        if kind == "aws_version_index":
            if scope != {"service": service} or capture["source_url"] != "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{}/index.json".format(service):
                raise ValueError("AWS index scope differs")
            versions = data.get("versions")
            if not isinstance(versions, dict) or not versions:
                raise ValueError("Missing AWS versions")
            for version, entry in versions.items():
                if not re.fullmatch(r"\d{14}", version) or entry["offerVersionUrl"] != "/offers/v1.0/aws/{}/{}/index.json".format(service, version):
                    raise ValueError("Invalid AWS version pointer")
                timestamp(entry["versionEffectiveBeginDate"])
                if entry.get("versionEffectiveEndDate"):
                    if timestamp(entry["versionEffectiveEndDate"]) <= timestamp(entry["versionEffectiveBeginDate"]):
                        raise ValueError("Invalid AWS version interval")
            coverage = dict(state="index_only", returned_entries=len(versions), scope="versions advertised by this service index")
        else:
            if set(scope) != {"service", "region", "version", "version_scope", "index_capture_id"}:
                raise ValueError("Unsupported AWS request scope")
            version = scope["version"]
            expected = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{}/{}/us-east-1/index.json".format(service, version)
            index = context.get(scope.get("index_capture_id"))
            if (scope.get("region") != "us-east-1" or capture["source_url"] != expected or data.get("version") != version
                    or index is None or index[0]["source_kind"] != "aws_version_index"):
                raise ValueError("AWS version/region/index differs")
            witness = json_source(index[1])
            if witness.get("offerCode") != service or witness["versions"].get(version) != scope["version_scope"]:
                raise ValueError("AWS version lacks its retained index witness")
            products, terms = data.get("products"), data.get("terms")
            if not isinstance(products, dict) or not products or not isinstance(terms, dict) or not terms:
                raise ValueError("Incomplete AWS snapshot")
            for sku, product in products.items():
                if product.get("sku") != sku or product.get("attributes", {}).get("regionCode") != "us-east-1":
                    raise ValueError("AWS product identity/region differs")
            termed = set()
            for term_type, skus in terms.items():
                if not isinstance(skus, dict):
                    raise ValueError("Malformed AWS terms")
                for sku, offers in skus.items():
                    if sku not in products or not offers:
                        raise ValueError("AWS term lacks product/offers")
                    termed.add(sku)
                    for offer, term in offers.items():
                        if term.get("sku") != sku or not term.get("priceDimensions"):
                            raise ValueError("Incomplete AWS price dimensions")
                        for code, dimension in term["priceDimensions"].items():
                            if dimension.get("rateCode") != code:
                                raise ValueError("AWS rate identity differs")
                            value = dict(product=products[sku], term={k: v for k, v in term.items() if k != "priceDimensions"}, dimension=dimension)
                            emit(code, "aws_sku_dimension", ["terms", term_type, sku, offer, "priceDimensions", code], value,
                                 dict(service=service, sku=sku, term_type=term_type, offer_id=offer, region="us-east-1"), term.get("effectiveDate"))
            for sku in sorted(set(products) - termed):
                emit(sku, "aws_unpriced_product", ["products", sku], products[sku], dict(service=service, region="us-east-1"))
            coverage = dict(state="complete_returned_snapshot", products=len(products), scope="this source version and us-east-1 only")
    elif kind == "deepinfra_api":
        if capture["source_url"] != "https://api.deepinfra.com/models/list":
            raise ValueError("DeepInfra API source differs")
        data = json_source(raw)
        if not isinstance(data, list) or not data:
            raise ValueError("Incomplete historical DeepInfra catalog")
        seen = set()
        for i, model in enumerate(data):
            mid = model.get("model_name") if isinstance(model, dict) else None
            if not isinstance(mid, str) or not mid or mid in seen:
                raise ValueError("Duplicate or missing historical model ID")
            if model.get("private") or model.get("is_private") or model.get("is_public") is False or model.get("visibility") == "private":
                raise ValueError("Private historical models cannot be retained")
            seen.add(mid)
            emit(mid, "deepinfra_model", [i], model, {})
        coverage = dict(state="complete_returned_snapshot", models=len(data), scope="returned public archive catalog; availability not inferred")
    else:
        if urlsplit(capture["source_url"]).path.rstrip("/") not in ("/pricing", "/models"):
            raise ValueError("DeepInfra HTML source differs")
        parser = Tables()
        try:
            text = decoded(raw).decode("utf-8")
        except UnicodeError:
            text = None
        if text is not None:
            parser.feed(text)
        parser.close()
        if parser.table is not None or parser.row is not None or parser.cell is not None:
            raise ValueError("Incomplete historical table")
        for ti, table in enumerate(parser.tables):
            if not table:
                continue
            for ri, cells in enumerate(table[1:], 1):
                if not cells:
                    continue
                links = cells[0]["links"]
                linked = len(links) == 1 and re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+", links[0])
                mid = links[0][1:] if linked else "table/{}/row/{}".format(ti, ri)
                emit(mid, "deepinfra_table_row", dict(table=ti, row=ri),
                     dict(headers=table[0], cells=cells, alignment_verified=len(cells) == len(table[0])),
                     dict(source_url=capture["source_url"], identity_basis="explicit_model_link" if linked else "document_local"))
        coverage = dict(state="unparsed_text_encoding" if text is None else "tables_only" if parser.tables else "no_structured_tables", tables=len(parser.tables),
                        scope="exact bytes retained; encoding not guessed" if text is None else "visible table rows only; scripts and narrative retained in exact source bytes")
    coverage.update(kind="coverage", capture_id=capture["id"], provider=capture["provider"], extractor=EXTRACTOR,
                    assertion_count=len(assertions), comparison_eligible=False)
    return assertions, coverage
