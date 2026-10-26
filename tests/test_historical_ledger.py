"""Evidence reconstruction, atomicity and conservative historical semantics."""
import base64
import copy
import contextlib
import fcntl
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import historical_ledger as ledger
from scripts import historical_sources as sources
from scripts.import_historical_evidence import from_input


def wire(value):
    return json.dumps(value, separators=(",", ":")).encode()


def meta(kind, url, scope=None, **extra):
    result = dict(provider="bedrock" if kind.startswith("aws_") else "deepinfra", source_kind=kind,
                  source_url=url, replay_url=None, retrieved_at="2026-10-26T08:00:00Z", archive_capture_at=None,
                  archive_digest=None, source_published_at=None, request_scope=scope or {})
    result.update(extra)
    return result


def archives(models=None, compressed=False, html=None, stamps=None):
    models = models or [[dict(model_name="old/model-v1", pricing=dict(type="tokens", cents_per_input_token=0.00001,
                                                                  cents_per_output_token=None), deprecated=123)]]
    stamps = stamps or ["20240417000000", "20240422000000", "20240501000000"][:len(models)]
    url = "https://deepinfra.com/pricing" if html is not None else "https://api.deepinfra.com/models/list"
    bodies = [html.encode()] if html is not None else [wire(m) for m in models]
    if compressed:
        bodies = [gzip.compress(b, mtime=0) for b in bodies]
    digests = [base64.b32encode(hashlib.sha1(b).digest()).decode() for b in bodies]
    query = "https://web.archive.org/cdx/search/cdx?url={}&matchType=exact&output=json&filter=statuscode:200&fl=timestamp,original,mimetype,statuscode,digest&limit=5001&to=20261026000000".format(url)
    rows = [["timestamp", "original", "mimetype", "statuscode", "digest"]]
    rows += [[stamp, url, "text/html" if html is not None else "application/json", "200", digest] for stamp, digest in zip(stamps, digests)]
    result = [dict(label="index", metadata=meta("archive_index", query, dict(target_url=url)), body=wire(rows))]
    for i, (stamp, body, digest) in enumerate(zip(stamps, bodies, digests)):
        result.append(dict(label="capture-" + str(i), body=body,
            metadata=meta("deepinfra_html" if html is not None else "deepinfra_api", url, dict(index_label="index"),
                          replay_url="https://web.archive.org/web/{}id_/{}".format(stamp, url),
                          archive_capture_at=sources.archive_time(stamp), archive_digest=digest)))
    return result


def aws():
    service, version = "AmazonBedrock", "20230928150907"
    publication = "2023-09-28T15:09:07Z"
    interval = dict(versionEffectiveBeginDate="2023-09-28T00:00:00Z", versionEffectiveEndDate="",
                    offerVersionUrl="/offers/v1.0/aws/{}/{}/index.json".format(service, version))
    base = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/" + service
    index = dict(offerCode=service, publicationDate=publication, versions={version: interval})
    product = dict(sku="SKU", attributes=dict(regionCode="us-east-1", model="old-1", servicecode=service))
    dimension = dict(rateCode="SKU.TERM.RATE", unit="1K tokens", beginRange="0", endRange="Inf",
                     pricePerUnit={"USD": "0.0003000000"}, appliesTo=[])
    data = dict(offerCode=service, version=version, publicationDate=publication, products={"SKU": product},
                terms={"OnDemand": {"SKU": {"SKU.TERM": dict(sku="SKU", effectiveDate="2023-09-28T00:00:00Z",
                    termAttributes={}, priceDimensions={"SKU.TERM.RATE": dimension})}}})
    return [dict(label="aws-index", body=wire(index), metadata=meta("aws_version_index", base + "/index.json", dict(service=service), source_published_at=publication)),
            dict(label="aws-file", body=wire(data), metadata=meta("aws_price_list", base + "/" + version + "/us-east-1/index.json",
                dict(service=service, region="us-east-1", version=version, version_scope=interval, index_label="aws-index"), source_published_at=publication))]


class HistoricalLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "ledger"

    def test_round_trip_exact_encoded_source_unknowns_and_three_distinct_times(self):
        descriptors = archives(compressed=True)
        result = ledger.ingest(self.root, descriptors)
        self.assertEqual(result["counts"], dict(capture=2, assertion=1, coverage=2, correction=0))
        _, rows = ledger.read_ledger(self.root)
        capture = next(r for r in rows if r["kind"] == "capture" and r["source_kind"] == "deepinfra_api")
        self.assertEqual(ledger.read_asset(self.root, capture["raw"], "sources"), descriptors[1]["body"])
        assertion = next(r for r in rows if r["kind"] == "assertion")
        self.assertFalse(assertion["comparison_eligible"])
        self.assertIsNone(assertion["source_record"]["pricing"]["cents_per_output_token"])
        self.assertIsNone(assertion["source_reported_effective_at"])
        self.assertIsNone(capture["source_published_at"])
        self.assertNotEqual(capture["retrieved_at"], capture["archive_capture_at"])
        self.assertNotIn("observed_at", assertion)
        self.assertEqual(assertion["source_record"]["deprecated"], 123)

    def test_aws_preserves_exact_dimensions_region_and_effective_date(self):
        ledger.ingest(self.root, aws())
        _, rows = ledger.read_ledger(self.root)
        assertion = next(r for r in rows if r["kind"] == "assertion")
        dim = assertion["source_record"]["dimension"]
        self.assertEqual(dim["pricePerUnit"], {"USD": "0.0003000000"})
        self.assertEqual(dim["unit"], "1K tokens")
        self.assertEqual(assertion["source_reported_effective_at"], "2023-09-28T00:00:00Z")
        self.assertEqual(assertion["identity_scope"]["region"], "us-east-1")

    def test_ordered_a_b_a_captures_are_not_digest_deduplicated(self):
        a = [dict(model_name="x/y", pricing=dict(type="tokens", cents_per_input_token="1"))]
        b = [dict(model_name="x/y", pricing=dict(type="tokens", cents_per_input_token="2"))]
        ledger.ingest(self.root, archives([a, b, a]))
        manifest, rows = ledger.read_ledger(self.root)
        self.assertEqual(manifest["counts"]["assertion"], 3)
        captures = [r for r in rows if r["kind"] == "capture" and r["source_kind"] == "deepinfra_api"]
        self.assertEqual(captures[0]["raw"], captures[2]["raw"])
        self.assertNotEqual(captures[0]["id"], captures[2]["id"])

    def test_idempotent_retry_retains_manifest_and_assets_byte_for_byte(self):
        descriptors = archives()
        ledger.ingest(self.root, descriptors)
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        ledger.ingest(self.root, descriptors)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_interrupted_manifest_commit_keeps_old_state_and_retry_recovers(self):
        first = archives()
        ledger.ingest(self.root, first)
        before = (self.root / "manifest.json").read_bytes()
        original = ledger._atomic

        def fail_manifest(path, content):
            if path.name == "manifest.json":
                raise OSError("fixture interruption")
            return original(path, content)

        second = aws()
        with patch.object(ledger, "_atomic", side_effect=fail_manifest), self.assertRaises(OSError):
            ledger.ingest(self.root, second)
        self.assertEqual((self.root / "manifest.json").read_bytes(), before)
        self.assertEqual(ledger.read_ledger(self.root)[0]["counts"]["capture"], 2)
        ledger.ingest(self.root, second)
        self.assertEqual(ledger.read_ledger(self.root)[0]["counts"]["capture"], 4)

    def test_small_segments_split_at_record_boundaries_and_enforce_single_row_cap(self):
        result = ledger.ingest(self.root, archives(), segment_cap=1800)
        self.assertGreater(len(result["segments"]), 1)
        self.assertTrue(all(r["uncompressed_bytes"] <= 1800 for r in result["segments"]))
        before = (self.root / "manifest.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "Single historical record"):
            ledger.ingest(self.root, aws(), segment_cap=50)
        self.assertEqual((self.root / "manifest.json").read_bytes(), before)

    def test_missing_assertion_and_forged_rehashed_assertion_fail_reconstruction(self):
        ledger.ingest(self.root, archives())
        manifest, rows = ledger.read_ledger(self.root)
        missing = [r for r in rows if r["kind"] != "assertion"]
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            ledger.validate_rows(missing, lambda ref: ledger.read_asset(self.root, ref, "sources"))
        forged = copy.deepcopy(rows)
        i = next(i for i, r in enumerate(forged) if r["kind"] == "assertion")
        forged[i]["source_record"]["pricing"]["cents_per_input_token"] = "0"
        forged[i] = ledger.record(forged[i])
        with self.assertRaisesRegex(ValueError, "extraction differs"):
            ledger.validate_rows(forged, lambda ref: ledger.read_asset(self.root, ref, "sources"))

    def test_tampered_source_and_manifest_totals_are_rejected(self):
        ledger.ingest(self.root, archives())
        manifest, rows = ledger.read_ledger(self.root)
        bad = copy.deepcopy(manifest)
        bad["counts"]["capture"] += 1
        with self.assertRaisesRegex(ValueError, "totals differ"):
            ledger.read_ledger(self.root, bad)
        ref = rows[0]["raw"]
        path = self.root / ref["path"]
        original = path.read_bytes()
        path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaisesRegex(ValueError, "checksum differs"):
            ledger.read_ledger(self.root)

    def test_symlinks_paths_missing_chunks_and_decompression_bombs_fail_closed(self):
        ledger.ingest(self.root, archives())
        manifest, rows = ledger.read_ledger(self.root)
        bad = copy.deepcopy(rows[0]["raw"])
        bad["path"] = "../escape"
        with self.assertRaises(ValueError):
            ledger.read_asset(self.root, bad, "sources")
        path = self.root / rows[0]["raw"]["path"]
        other = Path(self.temp.name) / "outside"
        other.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "symlink"):
            ledger.read_ledger(self.root)
        (self.root / manifest["segments"][0]["path"]).unlink()
        with self.assertRaises(FileNotFoundError):
            ledger.read_ledger(self.root)
        with patch.object(sources, "MAX_BYTES", 128), self.assertRaisesRegex(ValueError, "Decoded"):
            sources.decoded(gzip.compress(b"a" * 1000))

    def test_failed_or_ambiguous_inputs_never_advance_manifest(self):
        ledger.ingest(self.root, aws())
        before = (self.root / "manifest.json").read_bytes()
        model = dict(model_name="x/y", pricing=None)
        cases = [archives([[model, model]]), archives([[dict(model, private=True)]]), archives([[]])]
        mismatch = archives()
        mismatch[1]["metadata"]["archive_digest"] = "A" * 32
        cases.append(mismatch)
        unsafe = archives()
        unsafe[1]["metadata"]["source_url"] += "?api_key=fixture"
        cases.append(unsafe)
        wrong_region = aws()
        data = json.loads(wrong_region[1]["body"])
        data["products"]["SKU"]["attributes"]["regionCode"] = "other"
        wrong_region[1]["body"] = wire(data)
        cases.append(wrong_region)
        for case in cases:
            with self.subTest(case=cases.index(case)), self.assertRaises((ValueError, KeyError)):
                ledger.ingest(self.root, case)
            self.assertEqual((self.root / "manifest.json").read_bytes(), before)

    def test_duplicate_json_keys_and_nonfinite_values_rejected(self):
        for raw in [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}']:
            with self.assertRaises(ValueError):
                sources.json_source(raw)

    def test_html_placeholders_and_explicit_model_links_do_not_invent_prices(self):
        html = '<table><tr><th>Model</th><th>$ / 1M input</th></tr><tr><td><a href="/old/exact-v1">Old</a></td><td>-</td></tr></table>'
        ledger.ingest(self.root, archives(html=html))
        _, rows = ledger.read_ledger(self.root)
        row = next(r for r in rows if r["kind"] == "assertion")
        self.assertEqual(row["native_id"], "old/exact-v1")
        self.assertEqual(row["source_record"]["cells"][1]["text"], "-")
        self.assertNotIn("rates", row)
        self.assertFalse(row["comparison_eligible"])

    def test_corrections_append_references_and_preserve_original_assertions(self):
        a = [dict(model_name="x/y", pricing=None)]
        b = [dict(model_name="x/y", pricing=dict(type="tokens", cents_per_input_token="1"))]
        ledger.ingest(self.root, archives([a, b]))
        _, before = ledger.read_ledger(self.root)
        assertions = [r for r in before if r["kind"] == "assertion"]
        ledger.correct(self.root, assertions[1]["id"], assertions[0]["id"], "Explicit operator correction fixture", "2026-10-26T08:00:00Z")
        _, after = ledger.read_ledger(self.root)
        self.assertEqual(after[:len(before)], before)
        self.assertEqual(after[-1]["kind"], "correction")
        with self.assertRaisesRegex(ValueError, "later assertion"):
            ledger.correct(self.root, assertions[0]["id"], assertions[1]["id"], "reverse", "2026-10-26T08:00:00Z")

    def test_exclusive_lock_prevents_concurrent_writer(self):
        self.root.mkdir()
        with (self.root / ".ledger.lock").open("a") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "writer"):
                ledger.ingest(self.root, archives())

    def test_portable_input_rejects_traversal_and_body_mismatch(self):
        directory = Path(self.temp.name)
        path = directory / "input.json"
        body = b"test"
        (directory / "body").write_bytes(body)
        source = dict(label="fixture", body_path="body", body_sha256=ledger.sha(body), metadata={})
        path.write_bytes(wire(dict(schema_version=1, sources=[source])))
        self.assertEqual(from_input(path)[0]["body"], body)
        source["body_path"] = "../body"
        path.write_bytes(wire(dict(schema_version=1, sources=[source])))
        with self.assertRaises(ValueError):
            from_input(path)
        source["body_path"], source["body_sha256"] = "body", "0" * 64
        path.write_bytes(wire(dict(schema_version=1, sources=[source])))
        with self.assertRaisesRegex(ValueError, "hash/bytes"):
            from_input(path)

    def test_cli_inspection_and_exact_restore_never_overwrite_output(self):
        descriptors = archives(compressed=True)
        ledger.ingest(self.root, descriptors)
        _, rows = ledger.read_ledger(self.root)
        capture = next(r for r in rows if r["kind"] == "capture" and r["source_kind"] == "deepinfra_api")
        output = Path(self.temp.name) / "original.bin"
        argv = ["ledger", "--ledger-dir", str(self.root), "restore", "--capture-id", capture["id"], "--output", str(output)]
        with patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
            ledger.main()
        self.assertEqual(output.read_bytes(), descriptors[1]["body"])
        with patch("sys.argv", argv), self.assertRaises(FileExistsError):
            ledger.main()
        argv = ["ledger", "--ledger-dir", str(self.root), "inspect", "--provider", "deepinfra", "--native-id", "old/model-v1"]
        stdout = io.StringIO()
        with patch("sys.argv", argv), contextlib.redirect_stdout(stdout):
            ledger.main()
        inspected = json.loads(stdout.getvalue())
        self.assertEqual(len(inspected["assertions"]), 1)
        self.assertEqual(inspected["captures"][0]["id"], capture["id"])
        ledger.ingest(self.root, aws())
        argv = ["ledger", "--ledger-dir", str(self.root), "inspect", "--provider", "bedrock", "--sku", "SKU"]
        stdout = io.StringIO()
        with patch("sys.argv", argv), contextlib.redirect_stdout(stdout):
            ledger.main()
        self.assertEqual(json.loads(stdout.getvalue())["assertions"][0]["native_id"], "SKU.TERM.RATE")

    def test_missing_index_witness_and_forged_version_interval_fail(self):
        invalid = archives()[1:]
        with self.assertRaises(KeyError):
            ledger.ingest(self.root, invalid)
        invalid = aws()
        invalid[1]["metadata"]["request_scope"]["version_scope"]["versionEffectiveBeginDate"] = "2000-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "index witness"):
            ledger.ingest(self.root, invalid)
        self.assertFalse((self.root / "manifest.json").exists())

    def test_failed_discovery_retains_date_precision_without_a_fake_capture(self):
        ledger.ingest(self.root, archives())
        query = archives()[0]["metadata"]["source_url"].replace("matchType=exact", "matchType=prefix").replace("url=https://", "url=")
        ledger.record_discovery_failure(self.root, query, "2026-10-26", 503, "2026-10-26T08:00:00Z")
        manifest, rows = ledger.read_ledger(self.root)
        self.assertEqual(manifest["counts"]["capture"], 2)
        self.assertEqual(manifest["counts"]["coverage"], 3)
        self.assertIsNone(rows[-1]["capture_id"])
        self.assertNotIn("archive_capture_at", rows[-1])
        before = (self.root / "manifest.json").read_bytes()
        ledger.record_discovery_failure(self.root, query, "2026-10-26", 503, "2026-10-26T09:00:00Z")
        self.assertEqual((self.root / "manifest.json").read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "assert success"):
            ledger.record_discovery_failure(self.root, query, "2026-10-26", 200, "2026-10-26T08:00:00Z")


if __name__ == "__main__":
    unittest.main()
