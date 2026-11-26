"""Public-source regressions for the Hugging Face pause and Mistral model links."""
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers import mistral, novita
from providers.expanded import INVENTORY_PROVIDERS
from providers.policy import POLICIES, excluded_model_ids
from scripts.catalog_inventory import normalize_inventory
from scripts.collect import read_history, run
from scripts.normalize import ROOT, catalog

FIXTURES = Path(__file__).parent / 'fixtures'
HF = INVENTORY_PROVIDERS['huggingface']
PAUSED = {'Qwen/Qwen3.8-27B', 'deepseek-ai/DeepSeek-V4-Pro-0813', 'openai/gpt-oss-120b',
          'zai-org/GLM-5.3', 'zai-org/GLM-5.3-Flash'}


class Issue61And62Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.aliases = catalog()
        cls.prior_hf = json.loads((FIXTURES / 'provider-comparisons/huggingface.json').read_text())
        cls.failed_hf = (FIXTURES / 'issue-61/huggingface.json').read_text()
        cls.current_mistral = (FIXTURES / 'issue-62/mistral.html').read_text()

    def hf_responses(self, listing=None):
        return {HF.SOURCE: self.failed_hf if listing is None else listing,
                HF.documents[0]: self.prior_hf['documents'][0]['body']}

    def test_fixtures_match_captured_provenance(self):
        sources = json.loads((FIXTURES / 'issue-61/manifest.json').read_text())['sources']
        fixtures = {FIXTURES / 'issue-61' / name: evidence for name, evidence in sources.items()}
        fixtures[FIXTURES / 'issue-62/mistral.html'] = json.loads((FIXTURES / 'issue-62/manifest.json').read_text())
        for path, evidence in fixtures.items():
            body = path.read_bytes()
            with self.subTest(source=path.name):
                self.assertEqual(len(body), evidence['excerpt_bytes'])
                self.assertEqual(hashlib.sha256(body).hexdigest(), evidence['excerpt_sha256'])

    def test_huggingface_collects_native_data_when_all_five_reviewed_routes_are_paused(self):
        responses = self.hf_responses()
        with patch.dict(POLICIES, {'huggingface': {}}), patch('providers.expanded.fetch_text', side_effect=responses.__getitem__):
            before = HF.collect(self.aliases)
        self.assertIn('Reviewed Hugging Face Novita route missing or unavailable', before.parse_error)
        with patch('providers.expanded.fetch_text', side_effect=responses.__getitem__):
            after = HF.collect(self.aliases)
        self.assertIsNone(after.parse_error)
        self.assertEqual(excluded_model_ids('huggingface'), PAUSED)
        self.assertTrue(after.inventory_only)
        self.assertFalse(after.authoritative_catalog)
        self.assertEqual(after.records, [])
        self.assertEqual(after.source_payload, before.source_payload)
        native, _ = normalize_inventory('huggingface', after.source_payload, after.source_kind)
        self.assertEqual({row['native_id'] for row in native['records'] if row['kind'] == 'provider_route'}, PAUSED)
        self.assertTrue(all(not row['comparison_eligible'] for row in native['records']))

    def test_huggingface_inventory_only_retains_exact_reviewed_price_and_history_files(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            names = ('offerings.json', 'latest_prices.json', 'price_history.csv', 'price_history.json', 'changes.json')
            prior = {name: (ROOT / 'data' / name).read_bytes() for name in names}
            for name, body in prior.items():
                (data / name).write_bytes(body)
            with patch('providers.expanded.fetch_text', side_effect=self.hf_responses().__getitem__):
                self.assertEqual(run(data, ['huggingface'], strict=True), 0)
            self.assertEqual({name: (data / name).read_bytes() for name in names}, prior)
            status, = json.loads((data / 'status.json').read_text())['providers']
            self.assertEqual((status['state'], status['collection_scope'], status['offering_count']),
                             ('ok', 'inventory_only', 0))

    def test_returning_routes_stay_native_and_other_curated_bindings_remain_required(self):
        restored = json.dumps(self.prior_hf['catalog'])
        responses = self.hf_responses(restored)
        scoped = dict(self.aliases.for_provider('huggingface'))
        with patch('providers.expanded.fetch_text', side_effect=responses.__getitem__):
            result = HF.collect(scoped)
            extra = HF.collect(dict(scoped, **{'example/other-reviewed-model': 'example/other-reviewed-model'}))
        self.assertIsNone(result.parse_error)
        self.assertEqual(result.records, [])
        native, _ = normalize_inventory('huggingface', result.source_payload, result.source_kind)
        self.assertEqual({r['native_id'] for r in native['records'] if r['scope'].get('upstream_provider') == 'novita'}, PAUSED)
        self.assertFalse(extra.inventory_only)
        self.assertIn('example/other-reviewed-model', extra.parse_error)
        broken = self.hf_responses('{"data":[]}')
        with patch('providers.expanded.fetch_text', side_effect=broken.__getitem__):
            with self.assertRaisesRegex(ValueError, 'nonempty object listing'):
                HF.collect(self.aliases)

    def test_novita_direct_rates_for_the_same_models_are_independent(self):
        quotes = novita.parse((FIXTURES / 'issue-61/novita.json').read_text(), self.aliases).records
        direct = self.aliases.for_provider('novita')
        self.assertEqual({direct[row['provider_model_id']] for row in quotes},
                         set(self.aliases.for_provider('huggingface').values()))
        self.assertEqual(len(quotes), 5)
        self.assertTrue(all(row['provider'] == 'novita' and row['source_url'] == novita.SOURCE
                            and row['currency'] == 'USD' for row in quotes))

    def test_mistral_root_relative_links_preserve_the_six_original_quotes(self):
        old = (FIXTURES / 'issue-59/mistral.html').read_text()
        expected = mistral.parse_html(old, self.aliases).records
        self.assertEqual(len(expected), 6)
        self.assertCountEqual(mistral.parse_html(self.current_mistral, self.aliases).records, expected)

    def test_mistral_still_rejects_wrong_origin_link_and_duplicate_rendered_rows(self):
        link = '/models/codestral-25-08'
        row = re.search(r'<tr\b[^>]*>[^<]*(?:(?!</tr>).)*?<a\b[^>]*href="' + link +
                        r'"[^>]*>(?:(?!</tr>).)*</tr>', self.current_mistral, re.S)[0]
        dup = row.replace('href="' + link, 'href="/' + link)
        for body in (
            self.current_mistral.replace('href="' + link, 'href="https://example.com' + link),
            self.current_mistral.replace('href="' + link, 'href="//' + link),
            self.current_mistral.replace(row, row + dup, 1),
        ):
            with self.subTest(source_size=len(body)), self.assertRaisesRegex(ValueError, 'rendered row'):
                mistral.parse_html(body, self.aliases)
