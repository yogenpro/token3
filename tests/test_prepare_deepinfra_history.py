import json
from pathlib import Path
import tempfile
import unittest

from scripts.discover_historical_evidence import Discovery, replay_receipt_path, save
from scripts.historical_ledger import ingest, read_ledger
from scripts.prepare_deepinfra_history import prepare
from test_historical_ledger import archives


class PrepareDeepinfraHistoryTests(unittest.TestCase):
    def test_duplicate_index_rows_do_not_duplicate_import_labels_or_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'ledger'
            descriptors = archives(html='<table><tr><th>Model</th><th>Price</th></tr><tr><td>Old model</td><td>1.00</td></tr></table>')
            ingest(root, descriptors[:1])
            _, rows = read_ledger(root)
            capture = rows[0]
            stage = Path(directory) / 'stage'
            d = Discovery(stage, 1000000, 0)
            body, sha = d.blob(descriptors[0]['body'])
            index = dict(capture=capture, body_path=body, body_sha256=sha)
            meta = descriptors[1]['metadata']
            job = dict(provider='deepinfra', stamp='20240417000000', url=meta['source_url'], digest=meta['archive_digest'], index_capture_id=capture['id'], label='repeated')
            save(stage / 'plan.json', dict(profile='historical-native-v1', indexes=[index], jobs=[job, job]))
            body, sha = d.blob(descriptors[1]['body'])
            save(replay_receipt_path(stage, 'deepinfra', meta['replay_url'], meta['archive_digest']), dict(state='retrieved', body_path=body,
                body_sha256=sha, body_bytes=len(descriptors[1]['body']), retrieved_at=meta['retrieved_at']))
            result = prepare(stage)
            self.assertEqual(result['planned_replays'], 1)
            self.assertEqual(result['duplicate_index_entries'], 1)
            sources = json.loads((stage / 'validated-sources.json').read_bytes())['sources']
            self.assertEqual(len(sources), 2)
            self.assertEqual(len({s['label'] for s in sources}), 2)
