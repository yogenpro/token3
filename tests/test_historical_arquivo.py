import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

from scripts.historical_ledger import ingest, read_ledger
from scripts.historical_profiles import PROFILE
from scripts.historical_projection import project


def batch():
    url = 'https://console.groq.com/docs/models'
    stamp = '20240417000000'
    body = b'<table><tr><th>Model ID</th><th>Input USD per 1M tokens</th></tr><tr><td>exact/old</td><td>1.25</td></tr></table>'
    digest = base64.b32encode(hashlib.sha1(body).digest()).decode()
    index = (json.dumps(dict(url=url, timestamp=stamp, status='200', digest=digest, mime='text/html')) + '\n').encode()
    query = 'https://arquivo.pt/wayback/cdx?' + urlencode(dict(url=url, matchType='exact', output='json', limit='5001', to='20261026235959', resolveRevisits='true'))
    common = dict(provider='groq', retrieved_at='2026-10-27T08:00:00Z', source_published_at=None)
    return [dict(label='index', body=index, metadata=dict(common, source_kind='arquivo_index_v3', source_url=query, replay_url=None,
        archive_capture_at=None, archive_digest=None, request_scope=dict(profile=PROFILE, archive='arquivo.pt', target_url=url))),
        dict(label='body', body=body, metadata=dict(common, source_kind='arquivo_native_v3', source_url=url,
        replay_url='https://arquivo.pt/noFrame/replay/' + stamp + 'id_/' + url, archive_capture_at='2024-04-17T00:00:00+00:00',
        archive_digest=digest, request_scope=dict(profile=PROFILE, archive='arquivo.pt', index_label='index')))]


class ArquivoHistoryTests(unittest.TestCase):
    def test_distinct_archive_provenance_and_exact_witness_are_reconstructed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = ingest(root, batch())
            self.assertEqual(manifest['counts']['capture'], 2)
            public = project(root)
            self.assertTrue(public['captures'][1]['replay_url'].startswith('https://arquivo.pt/'))
            self.assertEqual(public['assertions'][0]['native_id'], 'exact/old')
            self.assertFalse(public['assertions'][0]['comparison_eligible'])
            self.assertEqual(public['assertions'][0]['evidence']['cells'][1]['text'], '1.25')
            before = (root / 'manifest.json').read_bytes()
            bad = batch(); bad[1]['body'] = b'changed body'
            with self.assertRaisesRegex(ValueError, 'digest'):
                ingest(root, bad)
            self.assertEqual(before, (root / 'manifest.json').read_bytes())

    def test_cross_archive_live_redirect_and_future_captures_are_rejected(self):
        for changes in [dict(replay_url='https://web.archive.org/web/20240417000000id_/https://groq.com/pricing/'),
                        dict(retrieved_at='2020-01-01T00:00:00Z'), dict(source_url='https://platform.openai.com/docs/pricing')]:
            with tempfile.TemporaryDirectory() as directory:
                data = copy.deepcopy(batch()); data[1]['metadata'].update(changes)
                with self.assertRaises(ValueError):
                    ingest(Path(directory), data)

    def test_successful_empty_index_is_a_lookup_check_not_a_price_or_retirement(self):
        data = batch(); meta = data[0]['metadata']
        check = dict(kind='coverage', capture_id=None, provider='groq', profile=PROFILE, provenance='historical_discovery_v3',
            source_url=meta['source_url'], target_url=meta['request_scope']['target_url'], checked_at='2026-10-27T09:00:00Z',
            state='archive_index_empty', http_status=200, transport_exit_code=None, comparison_eligible=False,
            archive_capture_at=None, archive_digest=None, index_capture_id=None)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ingest(root, data, checks=[check])
            _, rows = read_ledger(root)
            self.assertEqual(rows[-1]['state'], 'archive_index_empty')
            self.assertIsNone(rows[-1]['capture_id'])
            self.assertNotIn('retired', rows[-1])
            with self.assertRaises(ValueError):
                ingest(root, data, checks=[dict(check, http_status=404)])
