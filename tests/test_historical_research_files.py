import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.historical_research_files import read_report, write_report


class HistoricalResearchFilesTests(unittest.TestCase):
    def test_large_research_uses_bounded_lossless_checked_segments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'research.json'
            document = dict(policy='fixture', candidates=[dict(id=str(i), text='x' * 1000000) for i in range(7)])
            with patch('scripts.historical_research_files.MAX_BYTES', 2 * 1024 * 1024):
                write_report(path, document)
            manifest = json.loads(path.read_bytes())
            self.assertGreater(len(manifest['candidate_segments']), 1)
            self.assertTrue(all(r['uncompressed_bytes'] <= 2 * 1024 * 1024 for r in manifest['candidate_segments']))
            self.assertEqual(read_report(path), document)
            segment = path.parent / manifest['candidate_assets'] / manifest['candidate_segments'][0]['path']
            raw = bytearray(segment.read_bytes()); raw[-1] ^= 1; segment.write_bytes(raw)
            with self.assertRaises(ValueError):
                read_report(path)

    def test_small_report_round_trips_and_malicious_asset_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'research.json'
            write_report(path, dict(candidates=[dict(price='0.015')]))
            self.assertEqual(read_report(path), dict(candidates=[dict(price='0.015')]))
            path.write_text(json.dumps(dict(candidate_assets='../outside', candidate_count=0, candidate_segments=[])))
            with self.assertRaises(ValueError):
                read_report(path)
