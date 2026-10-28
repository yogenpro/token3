import json
from pathlib import Path
import tempfile
import unittest

from scripts.historical_ledger import ingest, read_snapshot
from scripts.historical_recovery_audit import build
from test_historical_arquivo import batch


class HistoricalRecoveryAuditTests(unittest.TestCase):
    def test_matching_bytes_in_another_archive_do_not_fabricate_a_direct_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); ledger = root / 'ledger'; data = batch(); ingest(ledger, data)
            body = data[1]['metadata']; stage = root / 'stage'; stage.mkdir()
            job = dict(provider='groq', url=body['source_url'], stamp='20240417000000', digest=body['archive_digest'])
            (stage / 'plan.json').write_text(json.dumps(dict(jobs=[job])))
            baseline = root / 'baseline.json'
            baseline.write_text(json.dumps([dict(provider='groq', archive_capture_at=body['archive_capture_at'],
                target_url=body['source_url'], archive_digest=body['archive_digest'], state='transport_failed')]))
            report = build(read_snapshot(ledger), [stage], baseline)
            self.assertEqual(report['original_backlog']['retained'], 0)
            self.assertEqual(report['original_backlog']['unresolved'], 1)
            missing = report['unresolved_targets'][0]
            self.assertEqual(missing['archive'], 'web.archive.org')
            self.assertEqual(len(missing['matching_retained_payload_capture_ids']), 1)
            self.assertEqual(missing['same_point_retained_capture_ids'], missing['matching_retained_payload_capture_ids'])
            self.assertEqual(missing['state'], 'budget_deferred')
