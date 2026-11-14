"""Current-source enrollment preserves exact billing and native boundaries."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.coverage_expansion import PUBLIC_SOURCES
from providers.coverage_quotes import REVIEWED_PROVIDERS, reviewed_quotes
from providers.reviewed_inventory import reviewed_quotes as gateway_quotes
from scripts.catalog_inventory import normalize_inventory
from scripts.collect import PROVIDERS, apply_snapshot
from scripts.normalize import catalog, normalize

FIXTURES = Path(__file__).parent / 'fixtures/provider-model-expansion'
REVIEW = json.loads((FIXTURES / 'review.json').read_text())
MANIFEST = json.loads((FIXTURES / 'manifest.json').read_text())
TIME = '2026-11-04T00:00:00Z'  # Fixture time only; never a production observation.
HASH = 'b' * 64


def source_bodies():
    return {info['source_url']: (FIXTURES / file).read_text()
            for file, info in MANIFEST['sources'].items()
            if not file.startswith(('openrouter-', 'vercel-'))}


def payload(provider):
    collector = PUBLIC_SOURCES[provider]
    sources = source_bodies()
    result = dict(format='token3.inventory-sources.v1', adapter=collector.adapter,
                  scope_note=collector.scope_note)
    if collector.adapter != 'public_documents':
        result['catalog'] = json.loads(sources[collector.SOURCE])
    urls = collector.documents or ((collector.SOURCE,) if collector.adapter == 'public_documents' else ())
    result['documents'] = [dict(source_url=url, body=sources[url]) for url in urls]
    return result


def gateway_payload(provider):
    files = sorted(FIXTURES.glob(provider + '-*.json'))
    return dict(catalog=dict(data=[r for file in files for r in json.loads(file.read_text())['data']]))


class CoverageExpansionTests(unittest.TestCase):
    def setUp(self):
        # Dated enrollment fixtures exercise the originally reviewed scopes;
        # current operator exclusions/stopped collection have separate tests.
        policy = patch.dict('providers.policy.POLICIES', {}, clear=True)
        policy.start()
        self.addCleanup(policy.stop)
        self.models, self.aliases = catalog()

    def quotes(self, provider, data=None):
        return reviewed_quotes(provider, data or payload(provider), self.aliases)

    def test_current_selection_is_complete_without_promoting_other_sources(self):
        old, added = set(REVIEW['baseline_model_ids']), set(REVIEW['new_model_ids'])
        self.assertEqual(len(old), 103)
        self.assertEqual(len(added), 66)
        self.assertFalse(old & added)
        self.assertEqual({m['id'] for m in self.models}, old | added)
        records = [r for provider in REVIEWED_PROVIDERS for r in self.quotes(provider)]
        for provider in ('openrouter', 'vercel'):
            records += gateway_quotes(provider, gateway_payload(provider), self.aliases, 'https://example.com/pricing')
        normalized = [normalize(r, self.aliases, TIME, HASH)[0] for r in records]
        self.assertEqual({o['model_id'] for o in normalized} & added, added)
        for provider, bindings in REVIEW['reviewed_bindings'].items():
            self.assertLessEqual(bindings.items(), self.aliases.for_provider(provider).items())
        self.assertNotIn('cohere/command-a-plus', self.aliases.for_provider('cohere'))
        self.assertNotIn('stepfun/step-5-preview', self.aliases.for_provider('stepfun'))
        self.assertNotIn('qwen3.5-4b', self.aliases.for_provider('openai'))
        self.assertNotIn('hy3-rl', self.aliases.for_provider('castform'))
        self.assertNotIn('text-embedding-3-large', self.aliases.for_provider('castform'))
        self.assertNotEqual(self.aliases['qwen/qwen3-235b-a22b-thinking-2507'],
                            self.aliases['qwen/qwen3-235b-a22b-instruct-2507'])
        self.assertNotEqual(self.aliases['perplexity/sonar'], 'perplexity/sonar')

    def test_all_registered_sources_are_public_with_separately_authorized_history(self):
        self.assertEqual(set(PUBLIC_SOURCES), {'cohere', 'ai21', 'perplexity', 'cerebras', 'castform', 'arcee',
            'stepfun', 'upstage', 'telnyx', 'typesafe', 'blackforestlabs', 'runway', 'stability', 'ideogram',
            'elevenlabs', 'byteplus', 'adobe', 'baidu'})
        self.assertLessEqual(PUBLIC_SOURCES.keys(), PROVIDERS.keys())
        published = json.loads((FIXTURES.parents[2] / 'config/historical_publication.json').read_text())
        self.assertEqual(len(published['providers']), 47)
        self.assertLessEqual(PUBLIC_SOURCES.keys(), set(published['providers']))

    def test_bounded_official_source_fixtures_keep_parent_and_fixture_hashes_distinct(self):
        for file, info in MANIFEST['sources'].items():
            with self.subTest(file=file):
                raw = (FIXTURES / file).read_bytes()
                self.assertEqual(len(raw), info['fixture_bytes'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), info['fixture_sha256'])
                self.assertLessEqual(len(raw), 256 * 1024)
                self.assertRegex(info['response_sha256'], r'^[a-f0-9]{64}$')
                self.assertTrue(info['source_url'].startswith('https://'))
                if file.startswith(('openrouter-', 'vercel-')):
                    self.assertNotEqual(info['response_sha256'], info['fixture_sha256'])

    def test_cerebras_uses_the_documented_default_format_and_unknown_capacities(self):
        records = self.quotes('cerebras')
        self.assertEqual([(r['provider_model_id'], r['input_per_million'], r['output_per_million']) for r in records],
                         [('gpt-oss-120b', .35, .75), ('qwen-3.8-27b', .99, 1.49)])
        self.assertTrue(all(r['context_window'] is None and r['max_output_tokens'] is None and r['cache_read_per_million'] is None for r in records))
        data = payload('cerebras')
        data['documents'][0]['body'] = data['documents'][0]['body'].replace('Pricing per token in USD.', 'Pricing per million tokens in USD.')
        with self.assertRaises(ValueError): self.quotes('cerebras', data)
        with self.assertRaises(ValueError): normalize_inventory('cerebras', json.dumps(data), 'api+documentation')
        for mutate in ('conditional', 'missing', 'duplicate', 'preview'):
            data = payload('cerebras')
            if mutate == 'conditional': data['catalog']['data'][0]['pricing']['request'] = '.01'
            elif mutate == 'missing': data['catalog']['data'].pop()
            elif mutate == 'duplicate': data['catalog']['data'].append(copy.deepcopy(data['catalog']['data'][0]))
            else: data['catalog']['data'][0]['preview'] = True
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): self.quotes('cerebras', data)

    def test_gateway_unreviewed_schedules_retain_base_observations_without_assuming_scope(self):
        data = gateway_payload('vercel')
        rows = gateway_quotes('vercel', data, self.aliases, 'https://ai-gateway.vercel.sh/v1/models')
        scheduled = next(r for r in rows if r['provider_model_id'] == 'deepseek/deepseek-v4-pro-0813')
        self.assertTrue(scheduled['pricing_scope_unverified'])
        offering, price = normalize(scheduled, self.aliases, TIME, HASH)
        self.assertTrue(offering['pricing_scope_unverified'])
        self.assertEqual((price['input_per_million'], price['output_per_million'], price['cache_read_per_million']), (.66, 1.98, .066))
        target = next(row for row in data['catalog']['data'] if row['id'] == 'deepseek/deepseek-v4-pro-0813')
        target['pricing'].pop('peak_pricing')
        rows = gateway_quotes('vercel', data, self.aliases, 'https://ai-gateway.vercel.sh/v1/models')
        self.assertTrue(next(r for r in rows if r['provider_model_id'] == target['id'])['pricing_scope_unverified'])
        other = next(row for row in data['catalog']['data'] if row['id'] == 'inception/mercury-3')
        other['pricing']['mandatory_request_fee'] = '.01'
        rows = gateway_quotes('vercel', data, self.aliases, 'https://ai-gateway.vercel.sh/v1/models')
        self.assertTrue(next(r for r in rows if r['provider_model_id'] == other['id'])['pricing_scope_unverified'])

    def test_gateway_nested_tier_conditions_quarantine_every_affected_prompt_band(self):
        for tier in ('flex', 'priority'):
            for long_context in (False, True):
                for component in ('peak_pricing', 'mandatory_request_fee'):
                    with self.subTest(tier=tier, long_context=long_context, component=component):
                        data = gateway_payload('vercel')
                        target = next(row for row in data['catalog']['data'] if row['id'] == 'google/gemini-3.1-pro-preview')
                        service = target['pricing']['service_tiers'][tier]
                        if not long_context:
                            service.pop('long_context')
                        before = gateway_quotes('vercel', data, self.aliases, 'https://ai-gateway.vercel.sh/v1/models')
                        service[component] = ({'multiplier': 2, 'windows': [{'start_minute_utc': 0, 'end_minute_utc': 840}]}
                                              if component == 'peak_pricing' else '.01')
                        rows = gateway_quotes('vercel', data, self.aliases, 'https://ai-gateway.vercel.sh/v1/models')
                        affected = [r for r in rows if r['provider_model_id'] == target['id'] and r['service_tier'] == tier]
                        self.assertEqual(len(affected), 2 if long_context else 1)
                        self.assertTrue(all(r.get('pricing_scope_unverified') is True for r in affected))
                        # The flag and explanatory notes may change; quote identities and base amounts must not.
                        self.assertEqual([normalize(r, self.aliases, TIME, HASH)[1] for r in rows],
                                         [normalize(r, self.aliases, TIME, HASH)[1] for r in before])
                        self.assertEqual([r for r in rows if r not in affected],
                                         [r for r in before if r['provider_model_id'] != target['id'] or r['service_tier'] != tier])
                        native_payload = dict(data, format='token3.inventory-sources.v1', adapter='vercel')
                        native, _ = normalize_inventory('vercel', json.dumps(native_payload), 'api')
                        record = next(r for r in native['records'] if r['native_id'] == target['id'])
                        self.assertEqual(record['billing']['rules']['service_tiers'][tier][component], service[component])
                        self.assertFalse(record['comparison_eligible'])

    def test_public_feeds_reject_partial_private_and_duplicate_snapshots(self):
        for provider in ('cerebras', 'castform'):
            for change in ('next', 'total', 'duplicate', 'private', 'empty'):
                data = payload(provider)
                if change == 'next': data['catalog']['next_page_token'] = 'next-public-page'
                elif change == 'total': data['catalog']['total_count'] = len(data['catalog']['data']) + 1
                elif change == 'duplicate': data['catalog']['data'].append(copy.deepcopy(data['catalog']['data'][0]))
                elif change == 'private': data['catalog']['data'][0]['private'] = True
                else: data['catalog']['data'] = []
                with self.subTest(provider=provider, change=change), self.assertRaises(ValueError):
                    normalize_inventory(provider, json.dumps(data), 'api')

    def test_castform_training_embeddings_and_unresolved_ids_are_not_text_quotes(self):
        data = payload('castform')
        native, _ = normalize_inventory('castform', json.dumps(data), 'api')
        self.assertEqual(len(native['records']), 22)
        training = [r for r in native['records'] if r['scope']['billing_product'] == 'training']
        self.assertEqual(len(training), 9)
        unpriced = next(r for r in training if r['native_id'] == 'tencent/Hy3')
        self.assertEqual(unpriced['rates'], [])
        self.assertTrue(all(not r['comparison_eligible'] for r in native['records']))
        records = self.quotes('castform')
        self.assertEqual(len(records), 11)
        self.assertFalse({r['provider_model_id'] for r in records} & {'hy3-rl', 'text-embedding-3-large'})
        for field, value in (('currency', 'EUR'), ('request_fee', .01), ('input_per_1m_tokens', None)):
            broken = copy.deepcopy(data)
            broken['catalog']['data'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.quotes('castform', broken)

    def test_arcee_rates_have_their_own_exact_billing_source(self):
        records = self.quotes('arcee')
        self.assertEqual(len(records), 5)
        flash = next(r for r in records if r['provider_model_id'] == 'zai-org/glm-5.3-flash')
        self.assertEqual((flash['input_per_million'], flash['output_per_million'], flash['cache_read_per_million']), (.15, .5, .03))
        for old, new in [('All prices are in USD.', 'All prices are in EUR.'), ('Prices per 1M Tokens.', 'Prices per 1K Tokens.'), ('Cached Input', 'Cache Storage')]:
            data = payload('arcee')
            data['documents'][0]['body'] = data['documents'][0]['body'].replace(old, new)
            with self.subTest(old=old), self.assertRaises(ValueError): self.quotes('arcee', data)

    def test_agent_quotes_do_not_use_private_orchestrator_or_legacy_search_prices(self):
        data = payload('perplexity')
        records = self.quotes('perplexity', data)
        self.assertEqual(len(records), 5)
        self.assertTrue(all('/agent-api/' in r['source_url'] for r in records))
        sonar = next(r for r in records if r['provider_model_id'] == 'perplexity/sonar')
        self.assertEqual((sonar['input_per_million'], sonar['output_per_million'], sonar['cache_read_per_million']), (.25, 2.5, .0625))
        native, _ = normalize_inventory('perplexity', json.dumps(data), 'documentation')
        self.assertTrue(any('private preview' in note for note in native['billing_notes']))
        self.assertTrue(all(not r['comparison_eligible'] for r in native['records']))
        for old, new in [ ('"currency": "USD"', '"currency": "EUR"'), ('Input (\\$/1M)', 'Input (\\$/1K)'), ('| 0.25 | 2.50 |', '| 0.25 (>100k) | 2.50 |') ]:
            broken = copy.deepcopy(data)
            document = next(d for d in broken['documents'] if '/agent-api/' in d['source_url'])
            self.assertIn(old, document['body'])
            document['body'] = document['body'].replace(old, new)
            with self.subTest(old=old), self.assertRaises(ValueError): self.quotes('perplexity', broken)

    def test_upstage_current_version_and_currency_witness_are_both_required(self):
        records = self.quotes('upstage')
        self.assertEqual([(r['provider_model_id'],r['input_per_million'],r['output_per_million'],r['cache_read_per_million']) for r in records],
            [('solar-pro4-260806', .3, 1.2, .06), ('solar-mini4-260922', .1, .4, .01)])
        for index, old, new in [(0, '"currencyCode":"USD"', '"currencyCode":"EUR"'),
                                (2, 'solar-pro4-260806', 'solar-pro4-261104'),
                                (2, '/1M tokens', '/1K tokens')]:
            broken = payload('upstage')
            # The model documents follow the pricing page and model directory.
            self.assertIn(old, broken['documents'][index]['body'])
            broken['documents'][index]['body'] = broken['documents'][index]['body'].replace(old, new)
            with self.subTest(old=old), self.assertRaises(ValueError): self.quotes('upstage', broken)

    def test_native_media_decisions_and_future_schedules_preserve_their_units(self):
        choices = {'runway':'runway.md','blackforestlabs':'blackforestlabs.md','stability':'stability.html',
                   'typesafe':'typesafe.md','stepfun':'stepfun.md','byteplus':'byteplus.md'}
        all_notes = {}
        for provider, file in choices.items():
            body = (FIXTURES / file).read_text()
            data = dict(format='token3.inventory-sources.v1', adapter='public_documents',
                        documents=[dict(source_url=MANIFEST['sources'][file]['source_url'],body=body)])
            native, _ = normalize_inventory(provider,json.dumps(data),'documentation')
            self.assertTrue(native['records'])
            self.assertTrue(all(not r['comparison_eligible'] for r in native['records']))
            if provider != 'typesafe':
                self.assertTrue(all(r['kind'] != 'model' for r in native['records']))
            self.assertTrue(all(r['rates'] == [] for r in native['records']))
            all_notes[provider] = '\n'.join(native['billing_notes'])
            if provider == 'runway':
                self.assertTrue(any('credits per second' in json.dumps(r['billing']) for r in native['records']))
            if provider == 'typesafe':
                self.assertTrue(any('Btok' in json.dumps(r['billing']) for r in native['records']))
                self.assertEqual({r['native_id'] for r in native['records'] if r['kind'] == 'model'}, {'jev-1.14.0', 'jev-1.13.0'})
            if provider == 'stepfun':
                self.assertTrue(any(r['metadata'].get('source_model_id') == 'step-5-preview' for r in native['records']))
            if provider == 'byteplus':
                self.assertTrue(any(r['metadata'].get('source_model_id') == 'seed-2-0-lite-260428' for r in native['records']))
        self.assertIn('November 9, 2026',all_notes['stepfun'])
        self.assertIn('Off',all_notes['byteplus'])

    def test_unstructured_public_pages_never_infer_zero_prices_or_execute_scripts(self):
        body = '<!doctype html><html><script>throw new Error("execute-me"); const price = "$999";</script><body><h1>API pricing</h1><p>Contact sales. Currency and model rates are unpublished.</p></body></html>'
        data = dict(format='token3.inventory-sources.v1',adapter='public_documents',
                    documents=[dict(source_url='https://example.com/pricing',body=body)])
        native,_ = normalize_inventory('adobe',json.dumps(data),'documentation')
        self.assertEqual(len(native['records']),1)
        row = native['records'][0]
        self.assertEqual(row['rates'],[])
        self.assertFalse(row['comparison_eligible'])
        self.assertNotIn('execute-me',row['billing']['text'])
        self.assertNotIn('$999',row['billing']['text'])
        self.assertIn('unpublished',row['billing']['text'])
        data['documents'][0]['body'] = '# Pricing\n' + 'a' * (128*1024)
        with self.assertRaises(ValueError): normalize_inventory('adobe',json.dumps(data),'documentation')

    def test_collector_keeps_native_evidence_and_last_good_quotes_after_review_failure(self):
        collector = PUBLIC_SOURCES['castform']
        sources = source_bodies()
        with patch('providers.coverage_expansion.fetch_text', side_effect=lambda url:sources[url]):
            good = collector.collect(self.aliases)
        self.assertFalse(good.inventory_only)
        self.assertIsNone(good.parse_error)
        offerings,latest,history,changes = {},{},[],[]
        apply_snapshot('castform',good,self.aliases,TIME,offerings,latest,history,changes)
        before = copy.deepcopy((offerings,latest,history,changes))
        data = json.loads(sources[collector.SOURCE])
        data['data'][0]['currency']='EUR'
        with patch('providers.coverage_expansion.fetch_text',return_value=json.dumps(data)):
            failed = collector.collect(self.aliases)
        self.assertIsNotNone(failed.parse_error)
        self.assertFalse(failed.inventory_only)
        self.assertEqual(failed.records,[])
        native,_ = normalize_inventory('castform',failed.source_payload,failed.source_kind)
        self.assertEqual(len(native['records']),22)
        self.assertTrue(any(r['currency']=='EUR' for row in native['records'] for r in row['rates']))
        with self.assertRaises(ValueError):
            apply_snapshot('castform',failed,self.aliases,TIME,offerings,latest,history,changes)
        self.assertEqual((offerings,latest,history,changes),before)


if __name__ == '__main__':
    unittest.main()
