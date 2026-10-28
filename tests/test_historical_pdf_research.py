import unittest

from scripts.historical_pdf_research import single_column_rates, layout_rates


class HistoricalPdfResearchTests(unittest.TestCase):
    def test_dual_rates_require_headers_preserve_unknowns_and_continue_across_pages(self):
        state = {}
        rows = list(layout_rates('''Table 6(a): Snowflake AI Features Table, Cortex AI Functions
Feature    Snowflake-managed compute (AI Credits per one million Tokens)
AI_COMPLETE – missing-header     1.00     2.00
Input                         Output
AI_COMPLETE – model-with-footnote5     1.80     9.00
''', state))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['rates'][0], dict(column='Input', amount='1.80', source_cell='1.80'))
        self.assertEqual(rows[0]['feature'], 'AI_COMPLETE – model-with-footnote5')
        self.assertEqual(rows[0]['unit'], 'AI Credits per one million Tokens')
        continued = list(layout_rates('''AI_COMPLETE – continued-model     0.12     -
Table 6(b): Other features
AI_COMPLETE – unrelated     0.01     0.02
''', state))
        self.assertEqual(len(continued), 1)
        self.assertIsNone(continued[0]['rates'][1]['amount'])

    def test_requires_same_line_explicit_unit_and_section(self):
        text = '''Cortex Complete – wrong-section     9.00
Table 6(a): Snowflake AI Features Credit Table, Cortex LLM Functions
Cortex Complete – no-unit     8.00
Feature    Snowflake-managed compute (Credits per one million Tokens)
Cortex Complete – llama3.1-405b     3.00
Legacy Features
Cortex Complete – llama2-chat-70b     0.45
Cortex Complete – ambiguous-input-output     1.00     2.00
Cortex Complete – missing-price     -
Table 6(b): Snowflake AI Features Credit Table, Fine-Tuning
Cortex Complete – wrong-table     7.00
'''
        rows = list(single_column_rates(text))
        self.assertEqual([(r['feature'], r['amount']) for r in rows], [
            ('Cortex Complete – llama3.1-405b', '3.00'), ('Cortex Complete – llama2-chat-70b', '0.45')])
        self.assertEqual(rows[1]['section'], 'Table 6(a): Legacy Features')
        self.assertEqual(rows[0]['unit'], 'Credits per one million Tokens')

    def test_never_transfers_header_or_amount_to_another_line(self):
        self.assertEqual(list(single_column_rates('''Table 6(a): Cortex LLM Functions
Feature Snowflake-managed compute (Credits per one million Tokens)
Cortex Complete – unaligned
0.12
''')), [])
