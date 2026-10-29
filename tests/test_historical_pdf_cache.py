"""PDF text reuse never substitutes for capture provenance or reconstruction."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pypdf
from scripts import historical_expansion as expansion
from scripts.historical_ledger import ingest, read_asset, read_ledger
from scripts.historical_sources import archive_time, extract
from test_historical_expansion import batch


class HistoricalPdfCacheTests(unittest.TestCase):
    def setUp(self):
        expansion._pdf_cache.clear()
        self.addCleanup(expansion._pdf_cache.clear)

    def test_exact_body_and_extractor_version_identify_immutable_cached_pages(self):
        reader = Mock(is_encrypted=False, pages=[Mock(extract_text=Mock(return_value="Original units: AI Credits"))])
        with patch.object(pypdf, "PdfReader", return_value=reader) as parse:
            first = expansion.pdf_pages(b"%PDF-fixture")
            self.assertIs(first, expansion.pdf_pages(b"%PDF-fixture"))
            self.assertEqual(first, ("Original units: AI Credits",))
            self.assertEqual(parse.call_count, 1)
            expansion.pdf_pages(b"%PDF-different")
            with patch.object(expansion, "EXTRACTOR", "fixture-next-version"):
                expansion.pdf_pages(b"%PDF-fixture")
            self.assertEqual(parse.call_count, 3)
            with patch.object(pypdf, "__version__", "unreviewed-version"), self.assertRaisesRegex(ValueError, "parser version"):
                expansion.pdf_pages(b"%PDF-fixture")

    def test_cache_has_byte_and_entry_bounds_and_does_not_retain_failures(self):
        reader = Mock(is_encrypted=False, pages=[Mock(extract_text=Mock(return_value="123456"))])
        with patch.object(pypdf, "PdfReader", return_value=reader) as parse, patch.object(expansion, "PDF_CACHE_BYTES", 10):
            for body in (b"one", b"two", b"one"):
                expansion.pdf_pages(body)
            self.assertEqual(parse.call_count, 3)
            self.assertLessEqual(sum(v[1] for v in expansion._pdf_cache.values()), 10)
        expansion._pdf_cache.clear()
        with patch.object(pypdf, "PdfReader", return_value=reader), patch.object(expansion, "PDF_CACHE_ENTRIES", 1):
            expansion.pdf_pages(b"one")
            expansion.pdf_pages(b"two")
            self.assertEqual(len(expansion._pdf_cache), 1)
        expansion._pdf_cache.clear()
        with patch.object(pypdf, "PdfReader", side_effect=ValueError("invalid PDF")), self.assertRaises(ValueError):
            expansion.pdf_pages(b"bad")
        self.assertEqual(len(expansion._pdf_cache), 0)
        with patch.object(pypdf, "PdfReader", return_value=reader), patch.object(expansion, "MAX_TEXT", 1), self.assertRaisesRegex(ValueError, "text cap"):
            expansion.pdf_pages(b"large")
        self.assertEqual(len(expansion._pdf_cache), 0)

    def test_warm_cache_preserves_distinct_capture_ids_and_rejects_bad_witnesses(self):
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=72, height=72)
        buffer = io.BytesIO()
        writer.write(buffer)
        body = buffer.getvalue()
        descriptors = batch("snowflake", body)
        second = copy.deepcopy(descriptors[1])
        second["label"] = "second"
        stamp = "20240517000000"
        second["metadata"]["archive_capture_at"] = archive_time(stamp)
        second["metadata"]["replay_url"] = "https://web.archive.org/web/{}id_/{}".format(stamp, second["metadata"]["source_url"])
        entries = json.loads(descriptors[0]["body"])
        entries.append([stamp] + entries[1][1:])
        descriptors[0]["body"] = json.dumps(entries).encode()
        with tempfile.TemporaryDirectory() as directory, patch.object(pypdf, "PdfReader", wraps=pypdf.PdfReader) as parse:
            root = Path(directory) / "ledger"
            ingest(root, descriptors + [second])
            _, rows = read_ledger(root)
            pages = [r for r in rows if r.get("assertion_type") == "historical_pdf_page"]
            self.assertEqual(len({r["capture_id"] for r in pages}), 2)
            self.assertEqual(parse.call_count, 1)
            captures = [r for r in rows if r["kind"] == "capture"]
            context = {r["id"]: (r, read_asset(root, r["raw"], "sources")) for r in captures}
            wrong = copy.deepcopy(captures[1])
            wrong["archive_digest"] = "A" * 32
            with self.assertRaisesRegex(ValueError, "digest/index witness"):
                extract(wrong, body, context)
            with self.assertRaisesRegex(ValueError, "retained index"):
                extract(captures[1], body, {})
            self.assertEqual(parse.call_count, 1)


if __name__ == "__main__":
    unittest.main()
