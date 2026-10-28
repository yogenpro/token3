import base64
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.historical_ledger import ingest, read_ledger
from scripts.historical_profiles import PROFILE


def batch(truncated=False):
    url = 'https://console.groq.com/docs/models'
    body = b'<table><tr><th>Model ID</th><th>USD / 1M tokens</th></tr><tr><td>old/exact</td><td>2.5</td></tr></table>'
    digest = base64.b32encode(hashlib.sha1(body).digest()).decode()
    http = b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n' + body
    warc = gzip.compress(('WARC/1.0\r\nWARC-Type: response\r\nWARC-Protocol: h2\r\nWARC-Protocol: tls/1.3\r\n' +
        ('WARC-Truncated: length\r\n' if truncated else '') + 'WARC-Date: 2024-04-17T00:00:00Z\r\nWARC-Target-URI: ' + url +
        '\r\nWARC-Payload-Digest: sha1:' + digest + '\r\nContent-Length: ' + str(len(http)) + '\r\n\r\n').encode() + http + b'\r\n\r\n', mtime=0)
    filename = 'crawl-data/CC-MAIN-2024-18/segments/12345.67/warc/CC-MAIN-20240417000000-20240417030000-00001.warc.gz'
    row = dict(url=url, status='200', digest=digest, filename=filename, offset='200', length=str(len(warc)))
    index = gzip.compress(('com,groq,console)/docs/models 20240417000000 ' + json.dumps(row) + '\n').encode(), mtime=0)
    common = dict(provider='groq', source_published_at=None, replay_url=None, retrieved_at='2026-10-27T10:00:00Z')
    return [dict(label='index', body=index, metadata=dict(common, source_kind='commoncrawl_index_v4', archive_capture_at=None,
        archive_digest=None, source_url='https://data.commoncrawl.org/cc-index/collections/CC-MAIN-2024-18/indexes/cdx-00001.gz',
        request_scope=dict(profile=PROFILE, archive='commoncrawl', target_url=url, byte_start=100, byte_length=len(index)))),
        dict(label='body', body=warc, metadata=dict(common, source_kind='commoncrawl_native_v4', source_url=url,
        archive_capture_at='2024-04-17T00:00:00+00:00', archive_digest=digest,
        request_scope=dict(profile=PROFILE, archive='commoncrawl', index_label='index', storage_url='https://data.commoncrawl.org/' + filename,
                           byte_start=200, byte_length=len(warc))))]


class CommonCrawlHistoryTests(unittest.TestCase):
    def test_truncated_archive_is_retained_without_fabricating_a_complete_price_table(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); manifest = ingest(root, batch(truncated=True)); _, rows = read_ledger(root)
            self.assertEqual(manifest['counts']['capture'], 2)
            self.assertEqual(manifest['counts']['assertion'], 0)
            coverage = next(r for r in rows if r.get('state') == 'truncated_archived_response')
            self.assertEqual(coverage['truncation_reason'], 'length')
            self.assertFalse(coverage['comparison_eligible'])

    def test_exact_range_cdx_and_warc_prove_payload_without_browser_replay(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); manifest = ingest(root, batch()); _, rows = read_ledger(root)
            self.assertEqual(manifest['counts']['capture'], 2)
            evidence = next(r for r in rows if r['kind'] == 'assertion')
            self.assertEqual(evidence['native_id'], 'old/exact')
            self.assertEqual(evidence['source_record']['cells'][1]['text'], '2.5')
            self.assertFalse(evidence['comparison_eligible'])
            self.assertIsNone(next(r for r in rows if r['kind'] == 'capture')['replay_url'])

    def test_wrong_offset_date_digest_or_missing_witness_cannot_commit(self):
        for change in ('offset', 'date', 'digest', 'body'):
            with tempfile.TemporaryDirectory() as d:
                data = copy.deepcopy(batch()); meta = data[1]['metadata']
                if change == 'offset': meta['request_scope']['byte_start'] += 1
                elif change == 'date': meta['archive_capture_at'] = '2024-04-18T00:00:00Z'
                elif change == 'digest': meta['archive_digest'] = 'A' * 32
                else: data[1]['body'] += b'extra'
                with self.assertRaises(ValueError): ingest(Path(d), data)
                self.assertFalse((Path(d) / 'manifest.json').exists())

    def test_failed_payload_retains_its_exact_index_witness_without_a_price_assertion(self):
        with tempfile.TemporaryDirectory() as d:
            data = batch(); meta = data[1]['metadata']; scope = meta['request_scope']
            check = dict(kind='coverage', capture_id=None, provider='groq', profile=PROFILE, provenance='historical_discovery_v4',
                source_url=scope['storage_url'], target_url=meta['source_url'], checked_at=meta['retrieved_at'], state='http_failed',
                http_status=503, transport_exit_code=None, comparison_eligible=False, archive_capture_at=meta['archive_capture_at'],
                archive_digest=meta['archive_digest'], index_label='index', byte_start=scope['byte_start'], byte_length=scope['byte_length'])
            root = Path(d); manifest = ingest(root, data[:1], checks=[check])
            self.assertEqual(manifest['counts']['capture'], 1)
            self.assertEqual(manifest['counts']['assertion'], 0)
            self.assertEqual(manifest['counts']['coverage'], 2)
            before = (root / 'manifest.json').read_bytes()
            with self.assertRaises(ValueError): ingest(root, data[:1], checks=[dict(check, byte_start=201)])
            self.assertEqual(before, (root / 'manifest.json').read_bytes())
