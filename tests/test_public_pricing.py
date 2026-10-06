import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from providers import anthropic, azure, bedrock, gemini, openai, vertex
from providers.public_pricing import dated_rate
from scripts.normalize import catalog, normalize
from scripts.catalog_inventory import normalize_inventory

FIXTURES = Path(__file__).parent / 'fixtures'
AS_OF = date(2026, 10, 3)
TIME = '2026-10-03T23:55:00Z'


class PublicPricingTests(unittest.TestCase):
    def setUp(self):
        _, self.aliases = catalog()

    def parse(self, provider, extension='md', as_of=AS_OF):
        body = (FIXTURES / (provider.__name__.split('.')[-1] + '.' + extension)).read_text()
        if provider in (gemini, vertex, azure):
            return provider.parse(body, self.aliases, as_of)
        return provider.parse(body, self.aliases)

    def test_openai_standard_not_batch_and_explicit_prompt_bands(self):
        result = self.parse(openai)
        self.assertEqual(len(result.records), 3)
        short, long = [r for r in result.records if r['provider_model_id'] == 'gpt-5.4-2026-03-05']
        self.assertEqual((short['input_per_million'], short['output_per_million'], short['max_input_tokens']), (2.5, 15, 272000))
        self.assertEqual((long['input_per_million'], long['output_per_million'], long['min_input_tokens']), (5, 22.5, 272001))
        mini = next(r for r in result.records if 'mini' in r['provider_model_id'])
        self.assertEqual(mini['input_per_million'], 0.75)
        self.assertIsNone(mini['max_input_tokens'])
        self.assertEqual(mini['context_window'], 400000)
        self.assertEqual(mini['max_output_tokens'], 128000)

    def test_missing_openai_long_prompt_rates_cannot_become_a_cheaper_uniform_rate(self):
        body = (FIXTURES / 'openai.md').read_text().replace('| $5.00 | $0.50 | - | $22.50 |', '| - | - | - | - |')
        with self.assertRaises(ValueError):
            openai.parse(body, self.aliases)

    def test_anthropic_five_minute_writes_and_separate_cache_reads(self):
        result = self.parse(anthropic)
        self.assertEqual(len(result.records), 3)
        sonnet = next(r for r in result.records if 'sonnet' in r['provider_model_id'])
        self.assertEqual((sonnet['input_per_million'], sonnet['output_per_million']), (3, 15))
        self.assertEqual((sonnet['cache_read_per_million'], sonnet['cache_write_per_million']), (0.3, 3.75))
        self.assertEqual(sonnet['region'], 'global')

    def test_gemini_paid_tiers_not_free_batch_or_storage_charges(self):
        result = self.parse(gemini)
        self.assertEqual(len(result.records), 6)
        self.assertEqual({r['service_tier'] for r in result.records}, {'standard', 'priority', 'flex'})
        flash = next(r for r in result.records if r['provider_model_id'] == 'gemini-3.8-flash' and r['service_tier'] == 'standard')
        self.assertEqual((flash['input_per_million'], flash['output_per_million'], flash['cache_read_per_million']), (0.75, 3.75, 0.075))
        self.assertIsNone(flash['cache_write_per_million'])
        self.assertEqual((flash['max_input_tokens'], flash['max_output_tokens']), (1048576, 65536))
        self.assertIsNone(flash['context_window'])

    def test_introductory_prices_switch_on_announced_utc_date(self):
        for provider, extension in [(gemini, 'md'), (vertex, 'html')]:
            before = self.parse(provider, extension, date(2026, 12, 31))
            after = self.parse(provider, extension, date(2027, 1, 1))
            def quote(result):
                return next(r for r in result.records if r['provider_model_id'] == 'gemini-3.8-flash' and r['service_tier'] == 'standard' and r['region'] == 'global')
            self.assertEqual(quote(before)['input_per_million'], 0.75)
            self.assertEqual(quote(after)['input_per_million'], 1.5)
            self.assertEqual(quote(after)['output_per_million'], 7.5)
            self.assertEqual(quote(after)['cache_read_per_million'], 0.15)
            old, _ = normalize(quote(before), self.aliases, TIME, 'a' * 64)
            new, _ = normalize(quote(after), self.aliases, TIME, 'b' * 64)
            self.assertEqual(old['id'], new['id'])

    def test_vertex_endpoint_regions_and_service_tiers_remain_separate(self):
        result = self.parse(vertex, 'html')
        self.assertEqual(len(result.records), 15)
        global_quote = next(r for r in result.records if r['provider_model_id'] == 'gemini-3.8-flash' and r['service_tier'] == 'standard' and r['region'] == 'global')
        regional = next(r for r in result.records if r['provider_model_id'] == 'gemini-3.8-flash' and r['service_tier'] == 'standard' and r['region'] == 'non-global')
        self.assertEqual(global_quote['input_per_million'], 0.75)
        self.assertEqual(regional['input_per_million'], 0.825)
        self.assertEqual(regional['cache_read_per_million'], 0.0825)
        # Conflicting unlabeled regional Claude rows must not be guessed.
        claude = [r for r in result.records if r['provider_model_id'].startswith('claude-')]
        self.assertEqual({r['region'] for r in claude}, {'global'})
        self.assertEqual({r['provider_model_id'] for r in claude}, {'claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5@20251001'})

    def test_bedrock_units_runtime_and_real_regional_premium(self):
        result = self.parse(bedrock, 'json')
        self.assertEqual(len(result.records), 8)
        oss = next(r for r in result.records if r['provider_model_id'] == 'openai.gpt-oss-120b-1:0')
        self.assertEqual((oss['input_per_million'], oss['output_per_million']), (0.15, 0.6))
        sonnet = [r for r in result.records if r['provider_model_id'] == 'anthropic.claude-sonnet-4-6']
        self.assertEqual({r['input_per_million'] for r in sonnet}, {3, 3.3})
        self.assertEqual({r['cache_write_per_million'] for r in sonnet}, {3.75, 4.125})
        self.assertTrue(all('pricing.us-east-1.amazonaws.com' in r['source_url'] for r in result.records))

    def test_azure_uses_usd_per_million_not_thousand_or_batch_prices(self):
        result = self.parse(azure, 'json')
        self.assertEqual(len(result.records), 10)
        short = next(r for r in result.records if r['provider_model_id'] == 'gpt-5.4-2026-03-05' and r['service_tier'] == 'standard' and r['region'].startswith('global') and r['max_input_tokens'] == 272000)
        self.assertEqual((short['input_per_million'], short['output_per_million'], short['cache_read_per_million']), (2.5, 15, 0.25))
        self.assertTrue(any(r['region'].startswith('US data zone') for r in result.records))
        self.assertTrue(any(r['service_tier'] == 'priority' for r in result.records))
        self.assertTrue(any(r['min_input_tokens'] == 272001 for r in result.records))

    def test_price_band_and_region_ids_are_distinct_and_stable(self):
        for provider, extension in [(openai, 'md'), (anthropic, 'md'), (gemini, 'md'), (vertex, 'html'), (bedrock, 'json'), (azure, 'json')]:
            result = self.parse(provider, extension)
            ids = [normalize(r, self.aliases, TIME, result.source_sha256)[0]['id'] for r in result.records]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertFalse(result.authoritative_catalog)

    def test_versions_and_modalities_are_not_automatically_merged(self):
        for model in ('gpt-5.4-pro', 'gpt-5.4-nano', 'claude-sonnet-5-5', 'gemini-3.8-flash-cyber', 'gemini-3.8-flash-tts'):
            self.assertNotIn(model, self.aliases)

    def test_collector_archives_a_fetched_document_when_curated_parsing_fails(self):
        body = "# Changed official pricing page with complete contents"
        with patch('providers.openai.fetch_text', return_value=body):
            result = openai.collect(self.aliases)
        self.assertEqual(result.records, [])
        self.assertEqual(result.source_payload, body)
        self.assertIn('Missing document section', result.parse_error)

    def test_empty_or_changed_sources_are_failures(self):
        for provider, body in [(openai, 'Login required'), (anthropic, 'changed layout'), (gemini, 'new page'), (vertex, '<html>blocked</html>'), (bedrock, '{}'), (azure, '{"Items": []}')]:
            with self.subTest(provider=provider.__name__):
                with self.assertRaises(ValueError):
                    provider.parse(body, self.aliases)

    def test_ambiguous_units_missing_models_and_broken_dates_fail_closed(self):
        body = json.loads((FIXTURES / 'azure.json').read_text())
        for row in body['Items']:
            row['unitOfMeasure'] = '1K'
        with self.assertRaises(ValueError):
            azure.parse(json.dumps(body), self.aliases, AS_OF)
        incomplete = (FIXTURES / 'anthropic.md').read_text().replace('Claude Opus 4.6', 'Claude Opus 9')
        with self.assertRaises(ValueError):
            anthropic.parse(incomplete, self.aliases)
        with self.assertRaises(ValueError):
            dated_rate('$0.75 through December 31, 2026. $1.50 starting January 3, 2027.', AS_OF)

    def test_foundry_scope_preserves_openai_and_native_non_token_meters(self):
        payload = json.loads((FIXTURES / 'azure.json').read_text())
        before = azure.parse(json.dumps(payload), self.aliases, AS_OF).records
        original = next(dict(row) for row in payload['Items'] if azure.SKU.fullmatch(row['skuName'].lower())
                        and row.get('type') == 'Consumption' and row.get('isPrimaryMeterRegion') is True)
        other = dict(original, productName='Azure Mistral Models', serviceName='Foundry Models',
                     meterId='fixture-other-model', skuId='fixture-other-sku', retailPrice=0.0001, unitPrice=0.0001)
        capacity = dict(original, productName='Azure AI Foundry Provisioned Throughput Reservation',
                        serviceName='Foundry Models', meterId='fixture-capacity', skuId='fixture-capacity-sku',
                        skuName='Provisioned Managed', unitOfMeasure='1/Hour', type='Reservation', reservationTerm='1 Year')
        payload['Items'] += [other, capacity]
        self.assertEqual(before, azure.parse(json.dumps(payload), self.aliases, AS_OF).records)
        native, _ = normalize_inventory('azure', json.dumps(payload), 'api')
        unknown = next(r for r in native['records'] if r['native_id'] == 'fixture-other-model')
        self.assertEqual(unknown['metadata']['serviceName'], 'Foundry Models')
        fixed = next(r for r in native['records'] if r['native_id'] == 'fixture-capacity')
        self.assertEqual(fixed['rates'][0]['unit'], '1/Hour')
        self.assertEqual(fixed['scope']['type'], 'Reservation')
        self.assertFalse(fixed['comparison_eligible'])
        with patch('providers.azure.fetch_text', return_value=json.dumps(payload)) as fetch:
            result = azure.collect(self.aliases)
        selected = parse_qs(urlparse(fetch.call_args.args[0]).query)['$filter'][0]
        self.assertEqual(selected, "serviceName eq 'Foundry Models' and armRegionName eq 'eastus'")
        self.assertEqual(result.source_kind, 'api')
        self.assertEqual(len(json.loads(result.source_payload)['Items']), len(payload['Items']))
        self.assertEqual(len(result.records), 10)

    def test_non_openai_version_like_skus_cannot_be_canonical_openai_quotes(self):
        payload = json.loads((FIXTURES / 'azure.json').read_text())
        for row in payload['Items']:
            row['productName'] = 'Azure Mistral Models'
        with self.assertRaises(ValueError):
            azure.parse(json.dumps(payload), self.aliases, AS_OF)

    def test_azure_pagination_is_complete_and_rejects_untrusted_links(self):
        payload = json.loads((FIXTURES / 'azure.json').read_text())
        half = len(payload['Items']) // 2
        first = dict(Items=payload['Items'][:half], NextPageLink='https://prices.azure.com/api/retail/prices?page=2')
        second = dict(Items=payload['Items'][half:], NextPageLink=None)
        with patch('providers.azure.fetch_text', side_effect=[json.dumps(first), json.dumps(second)]):
            self.assertEqual(len(azure.collect(self.aliases).records), 10)
        first['NextPageLink'] = 'https://evil.example/prices'
        with patch('providers.azure.fetch_text', return_value=json.dumps(first)):
            with self.assertRaises(ValueError):
                azure.collect(self.aliases)
        with self.assertRaises(ValueError):
            azure.parse(json.dumps(first), self.aliases, AS_OF)

    def test_invalid_token_bands_are_rejected_before_storage(self):
        row = self.parse(openai).records[0]
        for metadata in [dict(min_input_tokens=-1), dict(max_input_tokens=-1), dict(min_input_tokens=300000, max_input_tokens=200000), dict(max_output_tokens=True)]:
            with self.assertRaises(ValueError):
                normalize(dict(row, **metadata), self.aliases, TIME, 'a' * 64)


if __name__ == '__main__':
    unittest.main()
