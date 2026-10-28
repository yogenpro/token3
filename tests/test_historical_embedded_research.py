import unittest

from scripts.historical_embedded_research import embedded_rows, deepinfra_rows, decoded_document_rows
from scripts.historical_archive_decoding import document_text
from unittest.mock import patch
import brotli
import json


class HistoricalEmbeddedResearchTests(unittest.TestCase):
    def test_decoded_document_rows_keep_original_table_position_and_native_ids(self):
        html = '''<table><tr><td>irrelevant</td></tr></table><h2>USD prices per 1M tokens</h2>
<table><tr><th>Model ID</th><th>Input price</th></tr><tr><td>exact/old-v1</td><td>$0.25</td></tr></table>'''
        rows = list(decoded_document_rows(html))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['source_pointer'], dict(table=1, row=1))
        self.assertEqual(rows[0]['native_id'], 'exact/old-v1')
        self.assertTrue(rows[0]['numeric_price_candidate'])
        self.assertEqual(rows[0]['source_record']['cells'][1]['text'], '$0.25')

    def test_brotli_decoder_is_bounded_and_deepinfra_json_is_never_evaluated(self):
        payload = dict(props=dict(pageProps=dict(models=[dict(full_name='exact/old-model', name='label', pricing=dict(cents_per_input_token='0.000001',
            rate_per_input_token_cached='0.5'), mmlu=99), dict(full_name='private/model', private=True, pricing=dict(cents_per_input_token='1'))])))
        html = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(payload) + '</script>'
        text, encoding = document_text(brotli.compress(html.encode()))
        self.assertEqual(text, html)
        self.assertEqual(encoding, 'brotli')
        rows = list(deepinfra_rows(text))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['native_id'], 'exact/old-model')
        self.assertEqual(rows[0]['amount_expression'], dict(cents_per_input_token='0.000001'))
        self.assertNotIn('mmlu', rows[0]['model'])
        self.assertEqual(rows[0]['model']['pricing']['rate_per_input_token_cached'], '0.5')
        with patch('scripts.historical_archive_decoding.MAX_BYTES', 32):
            with self.assertRaises(ValueError):
                document_text(brotli.compress(html.encode()))

    def test_placeholder_preserves_embedded_regions_unit_and_unknowns(self):
        text = '''<h1>Pricing</h1><table><tr><th>Models</th><th>Prompt per 1,000 tokens</th><th>Completion per 1,000 tokens</th></tr>
<tr><td>Old Model</td><td><span data-amount='{"regional":{"us-east":0.0015,"other":null}}' data-decimals="4">$-</span></td><td><span data-amount='{"regional":{"us-east":0.002}}'>$-</span></td></tr></table>'''
        rows = list(embedded_rows(text))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['amount_expression'], {'regional': {'us-east': '0.0015', 'other': None}})
        self.assertEqual(rows[0]['price_header'], 'Prompt per 1,000 tokens')
        self.assertEqual(rows[0]['cells'], ['Old Model', '$-', '$-'])
        self.assertIsNone(rows[0]['native_id'])
        self.assertEqual(rows[1]['column'], 2)

    def test_malformed_unaligned_and_spanning_tables_do_not_establish_prices(self):
        for text in ['''<table><tr><th>Model</th><th>Price</th></tr><tr><td>X</td><td><span data-amount='NaN'>-</span></td></tr></table>''',
                     '''<table><tr><th>Model</th><th>Price</th></tr><tr><td rowspan="2">X</td><td><span data-amount='1'>-</span></td></tr></table>''',
                     '''<table><tr><th>Model</th></tr><tr><td>X</td><td><span data-amount='1'>-</span></td></tr></table>''',
                     '''<table><tr><th>Model</th><th>Price</th></tr><tr><td>X</td><td><span data-amount='1'>-</span>''']:
            self.assertEqual(list(embedded_rows(text)), [])
