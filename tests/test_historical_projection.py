"""The public historical projection selects fields without promoting quotes."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.historical_ledger import ingest, record_discovery_failure
from scripts.historical_projection import project, project_assertion, public_url
from test_historical_ledger import archives, aws


class HistoricalProjectionTests(unittest.TestCase):
    def test_whitelist_drops_arbitrary_model_metadata_and_transport_details(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ingest(root, archives([[dict(model_name="old/model", pricing=dict(cents_per_input_token="0.000001", unknown_fee=None),
                collector_only="do-not-publish", metadata=dict(private_endpoint="do-not-publish"))]]))
            before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            public = project(root)
            self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()})
            self.assertNotIn("do-not-publish", json.dumps(public))
            self.assertNotIn(".bin.gz", json.dumps(public))
            self.assertNotIn("request_scope", json.dumps(public))
            self.assertEqual(public["assertions"][0]["evidence"]["pricing"]["unknown_fee"], None)
            self.assertFalse(public["assertions"][0]["comparison_eligible"])
            self.assertIsNone(public["assertions"][0]["source_reported_effective_at"])
            self.assertEqual(public["captures"][1]["archive_capture_at"], "2024-04-17T00:00:00+00:00")

    def test_aws_exact_amounts_units_and_effective_dates_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            ingest(Path(directory), aws())
            public = project(Path(directory))
            row = public["assertions"][0]
            self.assertEqual(row["evidence"]["dimension"]["pricePerUnit"], {"USD": "0.0003000000"})
            self.assertEqual(row["evidence"]["dimension"]["unit"], "1K tokens")
            self.assertEqual(row["source_reported_effective_at"], "2023-09-28T00:00:00Z")

    def test_unsafe_urls_or_credential_fields_in_selected_evidence_fail_closed(self):
        for url in ["https://example.com/?api_key=fixture", "https://user:pass@example.com/", "javascript:alert(1)"]:
            with self.assertRaises(ValueError):
                public_url(url)
        with tempfile.TemporaryDirectory() as directory:
            ingest(Path(directory), archives([[dict(model_name="old/model", pricing=dict(api_key="fixture"))]]))
            with self.assertRaisesRegex(ValueError, "Credential"):
                project(Path(directory))

    def test_unknown_assertion_type_needs_publication_review(self):
        with self.assertRaisesRegex(ValueError, "publication review"):
            project_assertion(dict(source_record={}, assertion_type="unreviewed_new_source"))

    def test_legacy_lookup_day_is_not_replaced_with_report_recording_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptors = archives()
            ingest(root, descriptors)
            query = descriptors[0]["metadata"]["source_url"].replace("matchType=exact", "matchType=prefix")
            record_discovery_failure(root, query, "2026-10-25", 503, "2026-10-26T10:00:00Z")
            check = project(root)["checks"][0]
            self.assertIsNone(check["checked_at"])
            self.assertEqual(check["checked_date"], "2026-10-25")
            self.assertEqual(check["recorded_at"], "2026-10-26T10:00:00Z")
