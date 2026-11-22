"""Regression coverage for DeepSeek's revised token-denominator sentence."""

import hashlib
import json
import unittest
from pathlib import Path

from providers.deepseek_pricing import parse_models
from providers.expanded import INVENTORY_PROVIDERS
from providers.reviewed_inventory import reviewed_quotes
from scripts.normalize import catalog


FIXTURES = Path(__file__).parent / "fixtures"


class DeepSeekIssue52Tests(unittest.TestCase):
    def setUp(self):
        _, self.aliases = catalog()
        self.collector = INVENTORY_PROVIDERS["deepseek"]
        self.source_excerpt = (FIXTURES / "issue-52/deepseek.html").read_bytes()
        self.current = self.source_excerpt.decode("utf-8")

    def quotes(self, body):
        payload = {"documents": [{"body": body, "source_url": self.collector.SOURCE}]}
        return reviewed_quotes("deepseek", payload, self.aliases, self.collector.fetch_source)

    def test_revised_sentence_preserves_native_rates_and_all_four_reviewed_quotes(self):
        manifest = json.loads((FIXTURES / "issue-52/deepseek-manifest.json").read_text())
        self.assertEqual(manifest["official_source"], self.collector.fetch_source)
        self.assertEqual(len(self.source_excerpt), manifest["excerpt_bytes"])
        self.assertEqual(hashlib.sha256(self.source_excerpt).hexdigest(), manifest["excerpt_sha256"])

        prior = json.loads((FIXTURES / "provider-comparisons/deepseek.json").read_text())
        prior_body = prior["documents"][0]["body"]
        expected = self.quotes(prior_body)
        self.assertEqual(len(expected), 4)
        self.assertEqual(self.quotes(self.current), expected)
        self.assertEqual(parse_models(self.current), parse_models(prior_body))

    def test_current_layout_rejects_unreviewed_units_versions_and_schedules(self):
        for original, replacement, error in (
            ("Model prices are listed per 1M tokens.", "Model prices are listed per 1K tokens.", "token denominator"),
            ("Model prices are listed per 1M tokens.", "Model prices are listed below.", "token denominator"),
            ("1M OUTPUT TOKENS", "1K OUTPUT TOKENS", "price dimension"),
            ("Peak hours are 01:00", "Peak hours are 02:00", "requires new review"),
            ("DeepSeek-V4.1-Flash-1017", "DeepSeek-V4.1-Flash-1026", "requires new review"),
        ):
            self.assertIn(original, self.current)
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, error):
                self.quotes(self.current.replace(original, replacement))
