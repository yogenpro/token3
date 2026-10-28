import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.historical_community_research import prepare
from scripts.historical_ledger import read_asset
from scripts.historical_research_files import read_report


class CommunityHistoryTests(unittest.TestCase):
    def fixture(self, root):
        bundles = {
            'llerandi/llm-price-tracker': {'LICENSE': 'MIT License\nCopyright (c) 2026 Llerandi', 'README.md': 'Publisher schema',
                'data/history_summary.json': json.dumps(dict(dates=['2026-01-01'], models={'local': dict(provider='Google', input=[1], output=[None])}))},
            'romanshumy/llm-prices-data': {'LICENSE-DATA.md': 'CC BY 4.0 attribution modelpricewatch.com', 'README.md': 'Publisher schema',
                'price-history.json': json.dumps({'other-local': dict(provider='Amazon', history=[dict(date='2024-02-05', input_per_mtok=2)])})},
        }
        receipts = []
        for repo, files in bundles.items():
            for name, text in files.items():
                raw = text.encode(); digest = hashlib.sha256(raw).hexdigest(); (root / digest).write_bytes(raw)
                receipts.append(dict(repo=repo, file=name, commit='a' * 40, http_status=200,
                    url=f'https://raw.githubusercontent.com/{repo}/{"a" * 40}/{name}', body_path=digest,
                    sha256=digest, bytes=len(raw), retrieved_at='2026-10-27T09:00:00Z'))
        (root / 'receipts.json').write_text(json.dumps(receipts))
        return receipts

    def test_license_attribution_exact_sources_and_uncertain_identity_survive(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); self.fixture(root); output = root / 'report.json'
            stats = prepare(root, output); report = read_report(output)
            self.assertEqual(stats['romanshumy/llm-prices-data']['earliest_reported_day'], '2024-02-05')
            self.assertEqual({r['reported_provider'] for r in report['candidates']}, {'Google', 'Amazon'})
            self.assertTrue(all(r['native_provider'] is None and r['native_id'] is None and not r['comparison_eligible'] for r in report['candidates']))
            self.assertEqual(report['candidates'][0]['source_record']['output'], [None])
            for source in report['sources']:
                raw = read_asset(root / 'report-assets', source['raw'], 'sources')
                self.assertEqual(hashlib.sha256(raw).hexdigest(), source['source_sha256'])

    def test_tampering_or_missing_license_cannot_write_partial_report(self):
        for damage in ('tamper', 'license'):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); receipts = self.fixture(root)
                if damage == 'tamper':
                    (root / receipts[0]['body_path']).write_bytes(b'other')
                else:
                    (root / 'receipts.json').write_text(json.dumps(receipts[1:]))
                with self.assertRaises(ValueError):
                    prepare(root, root / 'report.json')
                self.assertFalse((root / 'report.json').exists())
                self.assertFalse((root / 'report-assets').exists())

    def test_mismatched_date_axis_cannot_invent_aligned_prices(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); receipts = self.fixture(root)
            r = next(r for r in receipts if r['file'] == 'data/history_summary.json')
            data = json.loads((root / r['body_path']).read_bytes()); data['dates'].append('2026-01-02')
            raw = json.dumps(data).encode(); digest = hashlib.sha256(raw).hexdigest()
            (root / digest).write_bytes(raw); r.update(body_path=digest, sha256=digest, bytes=len(raw))
            (root / 'receipts.json').write_text(json.dumps(receipts))
            with self.assertRaisesRegex(ValueError, 'alignment'):
                prepare(root, root / 'report.json')
            self.assertFalse((root / 'report-assets').exists())
