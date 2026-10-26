"""Explicit identity/billing review, independent of native discovery."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers import anthropic, deepinfra, gemini, groq, novita, openai
from providers.common import observation
from providers.expanded import INVENTORY_PROVIDERS
from providers.reviewed_inventory import reviewed_quotes, service_bands, token_bands
from scripts.catalog_inventory import normalize_inventory
from scripts.collect import PROVIDERS, apply_snapshot
from scripts.normalize import catalog, normalize

FIXTURES = Path(__file__).parent / 'fixtures'
TIME = '2026-10-11T00:00:00Z'
HASH = 'a' * 64


def fixture(provider):
    extension = 'json' if provider in ('deepinfra', 'novita', 'vercel') else 'md'
    return (FIXTURES / (provider + '-reviewed-expansion.' + extension)).read_text()


class ReviewedExpansionTests(unittest.TestCase):
    def setUp(self):
        self.models, self.aliases = catalog()

    def parser(self, provider):
        selected = self.aliases.sources[provider.__name__.split('.')[-1]]
        parser = provider.parse_markdown if provider is groq else provider.parse
        return parser(fixture(provider.__name__.split('.')[-1]), selected)

    def gateway(self, rows=None):
        payload = json.loads(fixture('vercel'))
        if rows is not None:
            payload['data'] = rows
        return reviewed_quotes('vercel', {'catalog': payload}, self.aliases.sources['vercel'], INVENTORY_PROVIDERS['vercel'].SOURCE)

    def test_exact_new_identities_and_source_bindings_are_complete(self):
        self.assertEqual(len(self.models), 45)
        self.assertEqual(len(set(self.aliases.legacy.values())), 12)
        added = {m['id'] for m in self.models} - set(self.aliases.legacy.values())
        self.assertEqual(len(added), 33)
        self.assertEqual({v for source in self.aliases.sources.values() for v in source.values()} - set(self.aliases.legacy.values()), added)
        self.assertTrue(set(self.aliases.sources) <= set(PROVIDERS))
        self.assertNotIn('gpt-6.1-luna', self.aliases)
        self.assertNotEqual(self.aliases['gpt-6-sol'], self.aliases['gpt-6.1-sol'])
        self.assertNotEqual(self.aliases['claude-fable-5'], self.aliases['claude-fable-5-1'])
        for unknown in ('anthropic/claude-opus-5.5-fast', 'moonshotai/kimi-k3-fast', 'moonshotai/kimi-k2.7-code-highspeed', 'alibaba/qwen3.8-max-prime', 'deepseek/deepseek-v4.1-flash-p', 'nvidia/Nemotron-3-Embed-8B'):
            with self.subTest(alias=unknown):
                self.assertNotIn(unknown, self.aliases)

    def test_catalog_rejects_implicit_new_model_or_unbound_source_ids(self):
        model = 'openai/gpt-6-luna'
        for entry in ({'aliases': ['gpt-6-luna']},
                      {'aliases': ['gpt-6-luna'], 'reviewed_sources': {}},
                      {'aliases': ['gpt-6-luna'], 'reviewed_sources': {'openai': ['unbound-version']}}):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'catalog').mkdir()
                (root / 'catalog/models.yaml').write_text(json.dumps({'models': [{'id': model}]}))
                (root / 'catalog/aliases.yaml').write_text(json.dumps({model: entry}))
                with self.assertRaises(ValueError):
                    catalog(root)

    def test_an_identity_does_not_authorize_other_provider_quotes(self):
        self.assertIn('minimax/minimax-m3', self.aliases)
        self.assertNotIn('minimax/minimax-m3', self.aliases.for_provider('novita'))
        self.assertNotIn('minimax/minimax-m3', self.aliases.for_provider('openrouter'))
        with self.assertRaises(ValueError):
            normalize(observation('novita', 'minimax/minimax-m3', 0.1, 0.2, novita.SOURCE), self.aliases, TIME, HASH)
        with self.assertRaises(ValueError):
            normalize(observation('vertex', 'claude-opus-5-5', 4, 20, 'https://cloud.google.com/vertex-ai/generative-ai/pricing'), self.aliases, TIME, HASH)

    def test_every_new_canonical_identity_has_a_validated_quote(self):
        records = self.gateway()
        for provider in (openai, anthropic, gemini, deepinfra, novita, groq):
            records.extend(self.parser(provider).records)
        normalized = [normalize(r, self.aliases, TIME, HASH)[0] for r in records]
        added = {m['id'] for m in self.models} - set(self.aliases.legacy.values())
        self.assertEqual({o['model_id'] for o in normalized}, added)
        self.assertEqual(len({o['id'] for o in normalized}), len(normalized))
        self.assertTrue(all(r['currency'] == 'USD' for r in records))

    def test_openai_new_models_keep_short_long_cache_write_and_unknown_capacities(self):
        rows = self.parser(openai).records
        self.assertEqual(len(rows), 8)
        sol = [r for r in rows if r['provider_model_id'] == 'gpt-6.1-sol']
        self.assertEqual([(r['min_input_tokens'], r['max_input_tokens']) for r in sol], [(0, 272000), (272001, None)])
        self.assertEqual([(r['input_per_million'], r['output_per_million']) for r in sol], [(2, 10), (4, 15)])
        self.assertEqual([(r['cache_read_per_million'], r['cache_write_per_million']) for r in sol], [(0.1, 2.5), (0.2, 5)])
        self.assertTrue(all(r['service_tier'] == 'standard' and r['context_window'] is None and r['max_output_tokens'] is None for r in rows))

    def test_openai_new_long_rates_and_boundary_fail_closed(self):
        body = fixture('openai')
        for broken in (body.replace('| $4.00 | $0.20 | $5.00 | $15.00 |', '| - | - | - | - |'), body.replace('Long context: >272K input tokens.', 'Long context: >200K input tokens.'), body.replace('Prices per 1M tokens.', 'Prices per 1K tokens.')):
            with self.assertRaises(ValueError):
                openai.parse(broken, self.aliases.sources['openai'])

    def test_anthropic_cache_ttl_haiku_bands_and_limited_access(self):
        rows = self.parser(anthropic).records
        self.assertEqual(len(rows), 7)
        opus = next(r for r in rows if r['provider_model_id'] == 'claude-opus-5-5')
        self.assertEqual((opus['input_per_million'], opus['output_per_million'], opus['cache_read_per_million'], opus['cache_write_per_million']), (4, 20, 0.2, 5))
        fable = next(r for r in rows if r['provider_model_id'] == 'claude-fable-5-1')
        self.assertEqual(fable['cache_read_per_million'], 0.25)
        haiku = [r for r in rows if r['provider_model_id'] == 'claude-haiku-5-5']
        self.assertEqual([(r['min_input_tokens'], r['max_input_tokens'], r['input_per_million'], r['output_per_million']) for r in haiku], [(0, 100000, 0.1, 0.5), (100001, None, 0.5, 2.5)])
        self.assertTrue(all('5-minute' in r['pricing_notes'] for r in rows))
        self.assertIn('Limited availability', next(r for r in rows if r['provider_model_id'] == 'claude-mythos-5-1')['pricing_notes'])

    def test_missing_haiku_band_cannot_become_uniform_cheaper_pricing(self):
        body = '\n'.join(line for line in fixture('anthropic').splitlines() if 'for prompts over 100,000 tokens' not in line)
        with self.assertRaisesRegex(ValueError, 'Incomplete Haiku'):
            anthropic.parse(body, self.aliases.sources['anthropic'])

    def test_gemini_pro_preview_token_bands_not_batch_or_storage(self):
        rows = self.parser(gemini).records
        self.assertEqual(len(rows), 2)
        self.assertEqual([(r['input_per_million'], r['output_per_million'], r['cache_read_per_million']) for r in rows], [(2, 12, 0.2), (4, 18, 0.4)])
        self.assertEqual([(r['min_input_tokens'], r['max_input_tokens']) for r in rows], [(0, 200000), (200001, None)])
        self.assertTrue(all(r['service_tier'] == 'standard' and r['cache_write_per_million'] is None for r in rows))
        with self.assertRaises(ValueError):
            gemini.parse(fixture('gemini').replace('200k', '100k'), self.aliases.sources['gemini'])

    def test_novita_new_cache_decimal_prices_are_not_integer_billing_units(self):
        rows = self.parser(novita).records
        qwen = next(r for r in rows if r['provider_model_id'] == 'qwen/qwen3.8-27b')
        self.assertEqual((qwen['input_per_million'], qwen['output_per_million'], qwen['cache_read_per_million']), (0.42, 3, 0.085))
        self.assertIsNone(qwen['cache_write_per_million'])
        body = json.loads(fixture('novita'))
        row = next(r for r in body['data'] if r['id'] == 'qwen/qwen3.8-27b')
        row['pricing']['input_cache_read'].pop('price_per_m_decimal')
        with self.assertRaises(KeyError):
            novita.parse(json.dumps(body), self.aliases.sources['novita'])

    def test_gateway_units_half_open_boundaries_and_service_tiers(self):
        rows = self.gateway()
        self.assertEqual(len(rows), 60)
        sol = [r for r in rows if r['provider_model_id'] == 'openai/gpt-6.1-sol']
        self.assertEqual({r['service_tier'] for r in sol}, {'standard', 'priority', 'flex'})
        self.assertEqual({(r['min_input_tokens'], r['max_input_tokens']) for r in sol}, {(0, 272000), (272001, None)})
        short = next(r for r in sol if r['service_tier'] == 'standard' and not r['min_input_tokens'])
        self.assertEqual((short['input_per_million'], short['output_per_million']), (2, 10))
        self.assertTrue(all(r['provider'] == 'vercel' and 'not a direct upstream-provider quote' in r['pricing_notes'] for r in rows))
        self.assertFalse(any('fast' in r['provider_model_id'] for r in rows))

    def test_gateway_invalid_rates_gaps_overlap_and_incomplete_long_rates_fail_closed(self):
        base = {'input': '0.000001', 'output': '0.000002'}
        for value in (True, '-1', 'NaN', 'Infinity', None):
            with self.subTest(price=value):
                with self.assertRaises(ValueError):
                    token_bands(dict(base, input=value))
        for tiers in ([{'cost': '0.000001', 'min': 1}], [{'cost': '0.000001', 'min': 0, 'max': 100}, {'cost': '0.000002', 'min': 99}], [{'cost': '0.000001', 'min': 0, 'max': 100}], [{'cost': '0.000001', 'min': 0, 'currency': 'EUR'}]):
            with self.assertRaises(ValueError):
                token_bands(dict(base, input_tiers=tiers))
        with self.assertRaises(ValueError):
            service_bands(dict(base, long_context={'threshold': 200001, 'input': '0.000002'}))

    def test_gateway_currency_drift_is_not_silently_converted(self):
        rows = json.loads(fixture('vercel'))['data']
        rows[0]['pricing']['currency'] = 'EUR'
        with self.assertRaisesRegex(ValueError, 'currency changed'):
            self.gateway(rows)

    def test_gateway_missing_tracked_model_or_wrong_modality_is_not_partial_success(self):
        rows = json.loads(fixture('vercel'))['data']
        with self.assertRaises(ValueError):
            self.gateway(rows[1:])
        broken = copy.deepcopy(rows)
        broken[0]['type'] = 'image'
        with self.assertRaises(ValueError):
            self.gateway(broken)

    def test_reviewed_gateway_quote_failure_still_retains_full_native_source(self):
        payload = json.loads(fixture('vercel'))
        with patch('providers.expanded.fetch_text', return_value=json.dumps(payload)):
            valid = INVENTORY_PROVIDERS['vercel'].collect(self.aliases.for_provider('vercel'))
        self.assertFalse(valid.inventory_only)
        self.assertIsNone(valid.parse_error)
        native, _ = normalize_inventory('vercel', valid.source_payload, valid.source_kind)
        self.assertTrue(all(not r['comparison_eligible'] for r in native['records']))
        broken = copy.deepcopy(payload)
        broken['data'][0]['pricing']['input'] = '-1'
        with patch('providers.expanded.fetch_text', return_value=json.dumps(broken)):
            failed = INVENTORY_PROVIDERS['vercel'].collect(self.aliases.for_provider('vercel'))
        self.assertFalse(failed.inventory_only)
        self.assertTrue(failed.parse_error)
        self.assertEqual(json.loads(failed.source_payload)['catalog'], broken)
        self.assertEqual(failed.records, [])

    def test_adding_reviewed_gateway_quotes_cannot_retire_old_offerings(self):
        rows = self.gateway()
        with patch('providers.expanded.fetch_text', return_value=fixture('vercel')):
            result = INVENTORY_PROVIDERS['vercel'].collect(self.aliases.for_provider('vercel'))
        self.assertFalse(result.authoritative_catalog)
        offerings, latest, history, changes = {}, {}, [], []
        apply_snapshot('vercel', result, self.aliases, TIME, offerings, latest, history, changes)
        original = copy.deepcopy(history)
        result.records = [r for r in rows if r['provider_model_id'] == 'openai/gpt-6.1-sol']
        apply_snapshot('vercel', result, self.aliases, '2026-10-11T01:00:00Z', offerings, latest, history, changes)
        self.assertEqual(history, original)
        self.assertTrue(all(o['active'] for o in offerings.values()))


if __name__ == '__main__':
    unittest.main()
