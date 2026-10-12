import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.catalog_inventory import canonical
from scripts.normalize import ROOT
from scripts.native_history import (MANIFEST, POLICY, append_history, compact_history, iter_archive_lines,
                                    iter_history, load_manifest, verify_reconstruction)

FIRST = "2026-10-10T07:00:00Z"
SECOND = "2026-10-11T07:00:00Z"
THIRD = "2026-10-12T07:00:00Z"
A, B, C = "a" * 64, "b" * 64, "c" * 64
URL = "https://cloudbilling.googleapis.com/v1/services/FIXTURE/skus?currencyCode=USD&pageSize=500"


def record(time=FIRST, amount="0.1"):
    return dict(id="vertex-record", provider="vertex", native_id="services/FIXTURE/skus/1", kind="sku", label="Fixture",
                scope=dict(service="services/FIXTURE", regions=["us-east1"]), metadata={}, comparison_eligible=False,
                billing=dict(pricing_info=[dict(effectiveTime=time, pricingExpression=dict(usageUnit="token", tieredRates=[]))]),
                rates=[dict(dimension="tier", amount=amount, currency="USD", unit="token", conditions=dict(effective_time=time))])


def event(identifier="first", time=FIRST, fingerprint=A, after=None, kind="record_added", revision=1):
    return dict(id=identifier, provider="vertex", observed_at=time, catalog_sha256=fingerprint, record_id="vertex-record",
                revision=revision, kind=kind, after=record(time) if after is None else after)


def proofs():
    return {key: dict(catalog_sha256=key, source_kind="api+documentation", source_urls=[URL]) for key in (A, B, C)}


class NativeHistoryStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        self.events = [event(), event("observation", SECOND, B, kind="record_changed", revision=2),
                       event("rate-change", THIRD, C, record(THIRD, "0.2"), "record_changed", 3)]
        self.write_original()

    def write_original(self):
        self.original = ("".join(canonical(e) + "\n" for e in self.events)).encode()
        (self.root / "inventory_history.jsonl").write_bytes(self.original)

    def migrate(self, witnesses=None, limit=2048):
        return compact_history(self.root, proofs() if witnesses is None else witnesses, apply=True, limit=limit)

    def test_dry_run_changes_no_data_and_identifies_only_timestamp_observation(self):
        report = compact_history(self.root, proofs())
        self.assertEqual(report["observation_count"], 1)
        self.assertFalse((self.root / MANIFEST).exists())
        self.assertEqual((self.root / "inventory_history.jsonl").read_bytes(), self.original)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["inventory_history.jsonl"])

    def test_lossless_archive_reconstruction_order_ids_and_exact_timestamps(self):
        report = self.migrate()
        self.assertEqual(report["observation_count"], 1)
        self.assertFalse((self.root / "inventory_history.jsonl").exists())
        rows = list(iter_history(self.root))
        self.assertEqual([row for row, _ in rows], self.events)
        self.assertEqual([flag for _, flag in rows], [False, True, False])
        manifest = verify_reconstruction(self.root)
        self.assertEqual(b"".join(iter_archive_lines(self.root, manifest)), self.original)
        self.assertEqual(manifest["archive"]["sha256"], hashlib.sha256(self.original).hexdigest())
        self.assertTrue(all(ref["uncompressed_bytes"] <= 2048 for ref in manifest["segments"] + manifest["archive"]["segments"]))

    def test_same_price_revert_remains_real_event(self):
        self.events += [event("revert", THIRD, C, record(THIRD, "0.1"), "record_changed", 4)]
        self.write_original()
        self.migrate()
        rows = list(iter_history(self.root))
        self.assertEqual(rows[-1], (self.events[-1], False))

    def test_requires_two_sided_historical_request_evidence(self):
        witnesses = proofs()
        del witnesses[A]
        self.assertEqual(self.migrate(witnesses)["observation_count"], 0)
        self.assertEqual([row for row, _ in iter_history(self.root)], self.events)

    def test_explicit_range_and_unknown_parameter_remain_conservative(self):
        for parameter in ("startTime=2026-10-10T00%3A00%3A00Z", "unreviewed=true"):
            witnesses = proofs()
            witnesses[B]["source_urls"] = [URL + "&" + parameter]
            self.assertEqual(compact_history(self.root, witnesses)["observation_count"], 0)

    def test_units_currency_region_and_other_metadata_are_not_compacted(self):
        original = copy.deepcopy(self.events)
        for field, value in [("unit", "1k"), ("currency", "EUR")]:
            self.events = copy.deepcopy(original)
            self.events[1]["after"]["rates"][0][field] = value
            self.write_original()
            self.assertEqual(compact_history(self.root, proofs())["observation_count"], 0)
        self.events = copy.deepcopy(original)
        self.events[1]["after"]["scope"]["regions"] = ["eu-west1"]
        self.write_original()
        self.assertEqual(compact_history(self.root, proofs())["observation_count"], 0)

    def test_schedules_and_future_source_times_are_not_compacted(self):
        self.events[1]["after"]["billing"]["pricing_info"].append(copy.deepcopy(self.events[1]["after"]["billing"]["pricing_info"][0]))
        self.write_original()
        self.assertEqual(compact_history(self.root, proofs())["observation_count"], 0)
        self.events[1]["after"] = record("2026-10-11T08:00:00Z")
        self.write_original()
        self.assertEqual(compact_history(self.root, proofs())["observation_count"], 0)

    def test_past_as_of_anomaly_is_preserved_exactly_not_a_fake_tariff(self):
        self.events[1]["after"] = record("2026-04-01T00:00:00Z")
        self.write_original()
        self.assertEqual(self.migrate()["observation_count"], 1)
        self.assertEqual(list(iter_history(self.root))[1][0]["after"], self.events[1]["after"])

    def test_append_immutable_segments_and_retry_do_not_modify_original_archive(self):
        self.migrate()
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*.gz")}
        new = event("new", THIRD, C, record(THIRD, "0.3"), "record_changed", 4)
        append_history(self.root, [new, new])
        self.assertEqual(load_manifest(self.root)["event_count"], 4)
        for name, content in before.items():
            self.assertEqual((self.root / name).read_bytes(), content)
        metadata = (self.root / MANIFEST).read_bytes()
        append_history(self.root, [new])
        self.assertEqual((self.root / MANIFEST).read_bytes(), metadata)
        self.assertEqual([row for row, _ in iter_history(self.root)], self.events + [new])
        verify_reconstruction(self.root)

    def test_missing_corrupt_and_incomplete_segments_fail_not_partial_success(self):
        self.migrate()
        manifest = load_manifest(self.root)
        path = self.root / manifest["segments"][0]["path"]
        content = path.read_bytes()
        path.write_bytes(content[:-1])
        with self.assertRaises(ValueError):
            list(iter_history(self.root))
        path.write_bytes(content)
        manifest["event_count"] += 1
        (self.root / MANIFEST).write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            list(iter_history(self.root))

    def test_proof_corruption_and_unsafe_asset_path_fail_closed(self):
        self.migrate()
        manifest = load_manifest(self.root)
        proof = self.root / manifest["proofs"]["path"]
        proof.write_bytes(proof.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            list(iter_history(self.root))
        manifest["segments"][0]["path"] = "../outside.jsonl.gz"
        (self.root / MANIFEST).write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            list(iter_history(self.root))

    def test_duplicate_original_ids_and_oversized_rows_leave_legacy_usable(self):
        self.events.append(copy.deepcopy(self.events[0]))
        self.write_original()
        with self.assertRaises(ValueError):
            self.migrate()
        self.assertFalse((self.root / MANIFEST).exists())
        self.events.pop()
        self.write_original()
        with self.assertRaises(ValueError):
            self.migrate(limit=100)
        self.assertFalse((self.root / MANIFEST).exists())
        self.assertEqual((self.root / "inventory_history.jsonl").read_bytes(), self.original)

    def test_failure_before_manifest_publish_and_idempotent_resume(self):
        with patch("scripts.native_history.verify_reconstruction", side_effect=ValueError("fail")):
            with self.assertRaises(ValueError):
                self.migrate()
        self.assertFalse((self.root / MANIFEST).exists())
        self.assertEqual((self.root / "inventory_history.jsonl").read_bytes(), self.original)
        report = self.migrate()
        self.assertEqual(self.migrate(), report)
        # Interrupted unlink after a valid commit point is safely resumed.
        (self.root / "inventory_history.jsonl").write_bytes(self.original)
        self.assertEqual(self.migrate(), report)
        self.assertFalse((self.root / "inventory_history.jsonl").exists())

    def test_old_unmarked_rows_remain_unclassified_and_collector_cannot_mark_them(self):
        self.assertTrue(all(not flag for _, flag in iter_history(self.root)))
        self.migrate()
        marked = event("forged")
        marked["_observation"] = dict(policy=POLICY)
        with self.assertRaises(ValueError):
            append_history(self.root, [marked])

    def test_legacy_write_is_bounded_and_cannot_accept_observation_flags(self):
        original = (self.root / "inventory_history.jsonl").read_bytes()
        marked = event("forged")
        marked["_observation"] = dict(policy=POLICY)
        with self.assertRaises(ValueError):
            append_history(self.root, [marked])
        huge = event("huge")
        huge["payload"] = "x" * (16 * 1024 * 1024)
        with self.assertRaisesRegex(ValueError, "exceeds 16 MiB"):
            append_history(self.root, [huge])
        self.assertEqual((self.root / "inventory_history.jsonl").read_bytes(), original)

    def test_interrupted_append_retains_previous_manifest_and_retry_commits_once(self):
        self.migrate()
        before = (self.root / MANIFEST).read_bytes()
        new = event("new", THIRD, C, record(THIRD, "0.3"), "record_changed", 4)
        from scripts.native_history import _atomic

        def fail_manifest(path, content):
            if str(path).endswith("manifest.json"):
                raise OSError("interrupted commit")
            return _atomic(path, content)

        with patch("scripts.native_history._atomic", side_effect=fail_manifest):
            with self.assertRaises(OSError):
                append_history(self.root, [new])
        self.assertEqual((self.root / MANIFEST).read_bytes(), before)
        self.assertEqual([e for e, _ in iter_history(self.root)], self.events)
        append_history(self.root, [new])
        self.assertEqual(load_manifest(self.root)["event_count"], 4)
        self.assertEqual([e for e, _ in iter_history(self.root)], self.events + [new])

    def test_multi_segment_future_batch_is_bounded_and_preserves_every_event(self):
        self.migrate()
        events = [dict(event("large-" + str(i), THIRD, C, record(THIRD, "0.3"), "record_changed", 4), payload="x" * 2000) for i in range(6500)]
        old_count = len(load_manifest(self.root)["segments"])
        append_history(self.root, events)
        manifest = load_manifest(self.root)
        self.assertGreater(len(manifest["segments"]) - old_count, 1)
        self.assertTrue(all(r["uncompressed_bytes"] <= 16 * 1024 * 1024 for r in manifest["segments"]))
        self.assertEqual([e for e, _ in iter_history(self.root)], self.events + events)
        verify_reconstruction(self.root)

    def test_old_storage_fixture_append_is_backward_compatible(self):
        new = event("new", THIRD, C, record(THIRD, "0.3"), "record_changed", 4)
        append_history(self.root, [new])
        self.assertEqual([row for row, _ in iter_history(self.root)], self.events + [new])


class ProductionNativeHistoryTests(unittest.TestCase):
    def test_complete_original_archive_and_reconstruction_are_valid(self):
        manifest = verify_reconstruction(ROOT / "data")
        self.assertEqual(manifest["archive"]["sha256"], manifest["migration"]["input_sha256"])
        self.assertEqual(manifest["archive"]["bytes"], manifest["migration"]["input_bytes"])
        self.assertEqual(manifest["archive"]["event_count"], manifest["migration"]["event_count"])
        self.assertEqual(manifest["observation_count"], manifest["migration"]["observation_count"])


if __name__ == "__main__":
    unittest.main()
