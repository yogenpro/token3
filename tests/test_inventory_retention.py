import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers import vertex
from providers.common import Collection
from scripts.catalog_inventory import canonical, digest, normalize_inventory
from scripts.collect import run
from scripts.inventory_retention import catalog_semantics, google_latest_time, latest_google_request, semantic_record
from scripts.inventory_storage import history_content, prepare_catalog
from scripts.normalize import catalog


FIRST = "2026-10-10T07:00:00Z"
SECOND = "2026-10-11T07:00:00Z"
THIRD = "2026-10-12T07:00:00Z"
SKU_URL = "https://cloudbilling.googleapis.com/v1/services/FIXTURE/skus?currencyCode=USD&pageSize=500"
FIXTURES = Path(__file__).parent / "fixtures"


def payload(times=(FIRST,), nanos=750000):
    skus = []
    for i, time in enumerate(times):
        info = dict(effectiveTime=time, pricingExpression=dict(usageUnit="1k", baseUnit="token", baseUnitConversionFactor=1000,
                    tieredRates=[dict(startUsageAmount=0, unitPrice=dict(currencyCode="USD", units="0", nanos=nanos))]))
        skus.append(dict(name="services/FIXTURE/skus/" + str(i), serviceRegions=["us-east1"], description="Fixture SKU " + str(i), pricingInfo=[info]))
    return dict(cloud_billing_catalog=dict(service=dict(name="services/FIXTURE"), catalog=dict(skus=skus)),
                curated_pricing_document=dict(body="# Prices\n| Model | Price |\n|---|---|\n| A | $1 per token |\n"))


def collection(body, url=SKU_URL):
    encoded = json.dumps(body)
    return Collection([], url, hashlib.sha256(encoded.encode()).hexdigest(), source_payload=encoded,
                      source_kind="api+documentation", source_urls=[url])


def persist(path, row, artifact):
    target = path / row["latest_path"]
    target.parent.mkdir(exist_ok=True)
    if artifact is not None:
        target.write_text(json.dumps(artifact))


class NativeSemanticRetentionTests(unittest.TestCase):
    def test_latest_times_do_not_change_fingerprint_but_raw_fields_and_hashes_survive(self):
        first, before = normalize_inventory("vertex", json.dumps(payload()), "api+documentation", [SKU_URL], FIRST)
        second, after = normalize_inventory("vertex", json.dumps(payload((SECOND,))), "api+documentation", [SKU_URL], SECOND)
        self.assertEqual(before, after)
        self.assertNotEqual(first["records"], second["records"])
        self.assertEqual(next(r for r in first["records"] if r["kind"] == "sku")["billing"]["pricing_info"][0]["effectiveTime"], FIRST)
        self.assertEqual(next(r for r in second["records"] if r["kind"] == "sku")["rates"][0]["conditions"]["effective_time"], SECOND)
        self.assertNotEqual(collection(payload()).source_sha256, collection(payload((SECOND,))).source_sha256)
        snapshot = copy.deepcopy(first)
        catalog_semantics(first)
        self.assertEqual(first, snapshot)
        self.assertTrue(all(not r["comparison_eligible"] for r in second["records"]))

    def test_only_verified_unbounded_google_requests_get_the_exception(self):
        self.assertTrue(latest_google_request("vertex", "api+documentation", [SKU_URL, SKU_URL + "&pageToken=next"]))
        for urls, provider, kind in [([], "vertex", "api+documentation"),
                                     ([SKU_URL + "&startTime=" + FIRST], "vertex", "api+documentation"),
                                     ([SKU_URL + "&endTime=" + SECOND], "vertex", "api+documentation"),
                                     ([SKU_URL, SKU_URL + "&startTime=" + FIRST], "vertex", "api+documentation"),
                                     ([SKU_URL + "&futureParameter=1"], "vertex", "api+documentation"),
                                     ([SKU_URL, SKU_URL.replace("/skus?", "/skus/?") + "&startTime=" + FIRST], "vertex", "api+documentation"),
                                     ([SKU_URL.replace("https:", "http:")], "vertex", "api+documentation"),
                                     ([SKU_URL.replace("cloudbilling.googleapis.com", "example.com")], "vertex", "api+documentation"),
                                     ([SKU_URL], "azure", "api"), ([SKU_URL], "vertex", "documentation")]:
            with self.subTest(urls=urls, provider=provider, kind=kind):
                self.assertFalse(latest_google_request(provider, kind, urls))
        for urls in [None, [SKU_URL + "&startTime=" + FIRST], [SKU_URL + "&endTime=" + SECOND]]:
            with self.subTest(urls=urls):
                _, before = normalize_inventory("vertex", json.dumps(payload()), "api+documentation", urls, FIRST)
                _, after = normalize_inventory("vertex", json.dumps(payload((SECOND,))), "api+documentation", urls, SECOND)
                self.assertNotEqual(before, after)

    def test_schedules_unknown_dates_and_other_provider_effective_dates_remain_semantic(self):
        row = next(r for r in normalize_inventory("vertex", json.dumps(payload()), "api+documentation", [SKU_URL], FIRST)[0]["records"] if r["kind"] == "sku")
        for transform in [lambda r: r.update(provider="azure"), lambda r: r.update(kind="document_row"),
                          lambda r: r["billing"]["pricing_info"].append(copy.deepcopy(r["billing"]["pricing_info"][0])),
                          lambda r: r["billing"]["pricing_info"][0].update(effectiveTime="unknown"),
                          lambda r: r["billing"]["pricing_info"][0].update(effectiveTime="2026-99-99T07:00:00Z"),
                          lambda r: r["rates"][0]["conditions"].update(effective_time=SECOND)]:
            modified = copy.deepcopy(row)
            transform(modified)
            self.assertIsNone(google_latest_time(modified))
            self.assertEqual(semantic_record(modified, True), modified)
        self.assertEqual(semantic_record(row, True), row)  # No observation-time proof.
        modified = copy.deepcopy(row)
        modified["rates"][0]["conditions"]["promotion_effective_date"] = SECOND
        self.assertNotEqual(semantic_record(row, True, FIRST), semantic_record(modified, True, FIRST))
        self.assertEqual(modified["rates"][0]["conditions"]["promotion_effective_date"], SECOND)

    def test_unconfirmed_future_effective_dates_are_not_suppressed(self):
        _, first = normalize_inventory("vertex", json.dumps(payload()), "api+documentation", [SKU_URL], FIRST)
        for time in [SECOND, "2026-10-10T07:21:00Z"]:
            with self.subTest(time=time), tempfile.TemporaryDirectory() as directory:
                catalog, changed = normalize_inventory("vertex", json.dumps(payload((time,))), "api+documentation", [SKU_URL], FIRST)
                self.assertNotEqual(first, changed)
                sku = next(r for r in catalog["records"] if r["kind"] == "sku")
                self.assertIsNone(google_latest_time(sku, FIRST))
                self.assertEqual(semantic_record(sku, True, FIRST), sku)
                row, _, _ = prepare_catalog("vertex", "Vertex", collection(payload((time,))), FIRST, Path(directory), {})
                self.assertNotIn("google_pricing_observation", row)

    def test_aging_an_unchanged_snapshot_does_not_invent_record_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            row, artifact, _ = prepare_catalog("vertex", "Vertex", collection(payload()), FIRST, path, {})
            persist(path, row, artifact)
            aged, artifact, events = prepare_catalog("vertex", "Vertex", collection(payload()), "2026-10-10T21:00:00Z", path, {"vertex": row})
            self.assertEqual(aged["revision"], row["revision"])
            self.assertEqual(events, [])
            self.assertIsNone(artifact)
            self.assertEqual(aged["google_pricing_observation"]["default_effective_time"], FIRST)
            self.assertEqual(aged["google_pricing_observation"]["older_than_documented_window_count"], 1)

    def test_meaningful_changes_and_intraday_reverts_still_create_full_events(self):
        _, base = normalize_inventory("vertex", json.dumps(payload()), "api+documentation", [SKU_URL], FIRST)
        changes = []
        for field, value in [("usageUnit", "1M tokens"), ("baseUnitConversionFactor", 1000000)]:
            body = payload((SECOND,))
            body["cloud_billing_catalog"]["catalog"]["skus"][0]["pricingInfo"][0]["pricingExpression"][field] = value
            changes.append(body)
        for field, value in [("aggregationInfo", {"aggregationInterval": "MONTHLY"}), ("currencyConversionRate", 1.1), ("future_effective_date", THIRD)]:
            body = payload((SECOND,))
            body["cloud_billing_catalog"]["catalog"]["skus"][0]["pricingInfo"][0][field] = value
            changes.append(body)
        body = payload((SECOND,)); body["cloud_billing_catalog"]["catalog"]["skus"][0]["pricingInfo"][0]["pricingExpression"]["tieredRates"][0]["unitPrice"]["currencyCode"] = "EUR"; changes.append(body)
        body = payload((SECOND,)); body["cloud_billing_catalog"]["catalog"]["skus"][0]["serviceRegions"] = ["europe-west1"]; changes.append(body)
        body = payload((SECOND,)); body["cloud_billing_catalog"]["catalog"]["skus"][0]["description"] = "Changed metadata"; changes.append(body)
        body = payload((SECOND,)); body["cloud_billing_catalog"]["catalog"]["skus"][0]["pricingInfo"][0]["pricingExpression"]["tieredRates"][0]["startUsageAmount"] = 1000; changes.append(body)
        body = payload((SECOND,)); body["curated_pricing_document"]["body"] += "Price promotion applies after " + THIRD; changes.append(body)
        for body in changes:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                row, artifact, _ = prepare_catalog("vertex", "Vertex", collection(payload()), FIRST, path, {})
                persist(path, row, artifact)
                changed, _, events = prepare_catalog("vertex", "Vertex", collection(body), SECOND, path, {"vertex": row})
                self.assertNotEqual(changed["catalog_sha256"], base)
                self.assertEqual(changed["revision"], 2)
                self.assertTrue(events)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); index = {}; history = path / "history.jsonl"
            for n, nanos in enumerate([750000, 500000, 750000], 1):
                row, artifact, events = prepare_catalog("vertex", "Vertex", collection(payload((SECOND,), nanos)), SECOND, path, index)
                self.assertEqual(row["revision"], n)
                persist(path, row, artifact); index["vertex"] = row
                history.write_text(history_content(history, events))
                self.assertEqual(history.read_text(), history_content(history, events))
            changed = [json.loads(line) for line in history.read_text().splitlines() if json.loads(line)["kind"] == "record_changed"]
            self.assertEqual(len(changed), 2)
            self.assertTrue(all(e["google_pricing_time_mode"] == "latest" for e in changed))
            self.assertEqual([e["after"]["rates"][0]["amount"] for e in changed], ["0.0005", "0.00075"])

    def test_discoveries_absences_and_reappearances_are_not_suppressed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); index = {}; seen = []
            for revision, times in enumerate([(FIRST,), (SECOND, SECOND), (THIRD,), (THIRD, THIRD)], 1):
                row, artifact, events = prepare_catalog("vertex", "Vertex", collection(payload(times)), times[0], path, index)
                self.assertEqual(row["revision"], revision)
                persist(path, row, artifact); index["vertex"] = row
                seen.append([e for e in events if e.get("record_id") and (e.get("after") or {}).get("kind", "sku") == "sku"])
            self.assertEqual([e["kind"] for e in seen[1]], ["record_added"])
            self.assertEqual([e["kind"] for e in seen[2]], ["record_no_longer_listed"])
            self.assertEqual([e["kind"] for e in seen[3]], ["record_added"])
            self.assertEqual(seen[1][0]["record_id"], seen[3][0]["record_id"])
            self.assertIsNone(seen[2][0]["after"])

    def test_legacy_policy_upgrade_does_not_fabricate_a_revision_or_rewrite_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            row, artifact, events = prepare_catalog("vertex", "Vertex", collection(payload()), FIRST, path, {})
            artifact.pop("google_pricing_time_mode")
            artifact.pop("google_pricing_observed_at")
            artifact["catalog_sha256"] = digest(catalog_semantics(artifact))
            row["catalog_sha256"] = artifact["catalog_sha256"]
            row.pop("google_pricing_observation")
            persist(path, row, artifact)
            history = path / "history.jsonl"
            history.write_text("".join(canonical(e) + "\n" for e in events))
            original = history.read_bytes()
            updated, migrated, events = prepare_catalog("vertex", "Vertex", collection(payload((SECOND,))), SECOND, path, {"vertex": row})
            self.assertEqual(updated["revision"], row["revision"])
            self.assertEqual(migrated["changed_at"], FIRST)
            self.assertEqual(events, [])
            self.assertEqual(history_content(history, events).encode(), original)
            self.assertNotEqual(updated["catalog_sha256"], row["catalog_sha256"])
            self.assertEqual(migrated["google_pricing_time_mode"], "latest")
            persist(path, updated, migrated)
            again, unchanged, events = prepare_catalog("vertex", "Vertex", collection(payload((THIRD,))), THIRD, path, {"vertex": updated})
            self.assertIsNone(unchanged)
            self.assertEqual(events, [])
            self.assertEqual(again["catalog_sha256"], updated["catalog_sha256"])
            self.assertEqual(again["google_pricing_observation"]["default_effective_time"], THIRD)
            self.assertEqual(history.read_bytes(), original)

    def test_nonuniform_as_of_times_are_retained_exactly_and_scale_compactly(self):
        with tempfile.TemporaryDirectory() as directory:
            row, artifact, _ = prepare_catalog("vertex", "Vertex", collection(payload((FIRST, FIRST, "2026-10-10T07:10:00Z"))), FIRST, Path(directory), {})
            observed = row["google_pricing_observation"]
            self.assertEqual(observed["record_count"], 3)
            self.assertEqual(observed["older_than_documented_window_count"], 0)
            self.assertEqual(observed["default_effective_time"], FIRST)
            self.assertEqual(len(observed["exceptions"]), 1)
            for record in artifact["records"]:
                if record["kind"] == "sku":
                    self.assertEqual(observed["exceptions"].get(record["id"], observed["default_effective_time"]), google_latest_time(record))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            row, artifact, events = prepare_catalog("vertex", "Vertex", collection(payload((FIRST,) * 2000)), FIRST, path, {})
            persist(path, row, artifact)
            updated, artifact, events = prepare_catalog("vertex", "Vertex", collection(payload((SECOND,) * 2000)), SECOND, path, {"vertex": row})
            self.assertIsNone(artifact)
            self.assertEqual(events, [])
            self.assertLess(len(canonical(updated["google_pricing_observation"])), 200)
            self.assertEqual(updated["google_pricing_observation"]["record_count"], 2000)


class NativeObservationCollectionTests(unittest.TestCase):
    def test_checks_preserve_fresh_provenance_without_daily_catalog_or_history_writes(self):
        _, aliases = catalog()
        document = (FIXTURES / "vertex.html").read_text()
        def parsed(time):
            r = vertex.parse(document, aliases)
            body = payload((time,))
            body["curated_pricing_document"]["body"] = document
            source = collection(body)
            r.source_payload, r.source_sha256 = source.source_payload, source.source_sha256
            r.source_url, r.source_urls, r.source_kind = SKU_URL, [SKU_URL, vertex.SOURCE], "api+documentation"
            return r
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch("scripts.collect.vertex.collect", return_value=parsed(FIRST)), patch("scripts.collect.utc_now", return_value=FIRST):
                self.assertEqual(run(path, ["vertex"], strict=True), 0)
            files = [path / name for name in ["inventory_history.jsonl", "price_history.csv", "provider_catalogs/vertex.json"]]
            original = [p.read_bytes() for p in files]
            history_rows = json.loads((path / "price_history.json").read_text())
            with patch("scripts.collect.vertex.collect", return_value=parsed(SECOND)), patch("scripts.collect.utc_now", return_value=SECOND):
                self.assertEqual(run(path, ["vertex"], strict=True), 0)
            self.assertEqual(original, [p.read_bytes() for p in files])
            self.assertEqual(history_rows, json.loads((path / "price_history.json").read_text()))
            checks = [json.loads(line) for line in (path / "collection_checks.jsonl").read_text().splitlines()]
            self.assertEqual([r["google_pricing_observation"]["default_effective_time"] for r in checks], [FIRST, SECOND])
            self.assertNotEqual(checks[0]["source_sha256"], checks[1]["source_sha256"])
            self.assertEqual(checks[0]["catalog_sha256"], checks[1]["catalog_sha256"])
            reviewed_failure = parsed(THIRD)
            reviewed_failure.parse_error = "fixture reviewed parser failure"
            with patch("scripts.collect.vertex.collect", return_value=reviewed_failure), patch("scripts.collect.utc_now", return_value=THIRD):
                self.assertEqual(run(path, ["vertex"], strict=True), 1)
            self.assertEqual(original, [p.read_bytes() for p in files])
            native_good = json.loads((path / "collection_checks.jsonl").read_text().splitlines()[-1])
            self.assertEqual(native_good["state"], "error")
            self.assertEqual(native_good["google_pricing_observation"]["default_effective_time"], THIRD)
            self.assertEqual(json.loads((path / "status.json").read_text())["providers"][0]["last_success_at"], SECOND)
            with patch("scripts.collect.vertex.collect", side_effect=RuntimeError("fixture outage")), patch("scripts.collect.utc_now", return_value="2026-10-13T07:00:00Z"):
                self.assertEqual(run(path, ["vertex"], strict=True), 1)
            self.assertEqual(original, [p.read_bytes() for p in files])
            failed = json.loads((path / "collection_checks.jsonl").read_text().splitlines()[-1])
            self.assertEqual(failed["state"], "error")
            self.assertNotIn("google_pricing_observation", failed)
            snapshot = {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()}
            with patch("scripts.collect.vertex.collect", return_value=parsed(THIRD)), patch("scripts.collect.utc_now", return_value=THIRD):
                self.assertEqual(run(path, ["vertex"], dry_run=True, strict=True), 0)
            self.assertEqual(snapshot, {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
