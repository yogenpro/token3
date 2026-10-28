import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.historical_reports import load, validate
from scripts.historical_price_coverage import build, price_evidence
from scripts.historical_ledger import ingest
from scripts.historical_ledger import read_ledger, canonical, sha
from scripts.historical_profiles import PROFILE
from test_historical_expansion import batch


class BestEffortHistoricalReportsTests(unittest.TestCase):
    def test_relative_factors_without_absolute_prices_remain_unpriced(self):
        row = dict(assertion_type='deepinfra_model', provider='deepinfra', source_record=dict(pricing=dict(
            cents_per_input_token=None, cents_per_output_token=None, rate_per_input_token_cached='0.1', rate_per_service_tier_priority='2')))
        self.assertIsNone(price_evidence(row))

    def test_embedded_price_candidates_reconstruct_before_counting(self):
        from scripts.historical_embedded_research import capture_candidates
        body = b'''<table><tr><th>Models</th><th>Prompt per 1000 tokens</th></tr><tr><td>Old model</td><td><span data-amount='{"regional":{"us-east":0.03}}'>$-</span></td></tr></table>'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'ledger'
            ingest(root, batch('azure', body, 'https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/'))
            _, rows = read_ledger(root)
            capture = next(r for r in rows if r['kind'] == 'capture' and r['source_kind'] == 'archived_native_v2')
            candidates = list(capture_candidates(capture, body))
            path = Path(directory) / 'research.json'
            data = dict(policy='historical-embedded-price-research-v1', ledger_manifest_sha256=sha((root / 'manifest.json').read_bytes()), candidates=candidates)
            path.write_bytes(canonical(data))
            self.assertEqual(build(root, embedded_research=path)['providers']['azure']['embedded_price_candidates'], 1)
            data['candidates'][0]['amount_expression']['regional']['us-east'] = '0.01'
            data['candidates'][0]['id'] = sha(canonical({k:v for k,v in data['candidates'][0].items() if k != 'id'}))
            path.write_bytes(canonical(data))
            with self.assertRaisesRegex(ValueError, 'retained source'):
                build(root, embedded_research=path)

    def test_real_sources_preserve_conflicts_scope_and_unreviewed_status(self):
        data = load()
        self.assertEqual(len(data["sources"]), 9)
        self.assertTrue(all(c["comparison_eligible"] is False for c in data["claims"]))
        dated = [c for c in data["claims"] if c["reported_effective_date"] is not None]
        self.assertEqual(len(dated), 2)
        self.assertTrue(all(c["provider"] == "azure" and c["reported_effective_date"] == "2023-04-01" for c in dated))
        self.assertEqual(sum(c["confidence"] == "conflicting_reports" for c in data["claims"]), 2)
        nebius = next(c for c in data["claims"] if c["provider"] == "nebius")
        self.assertIsNone(nebius["native_id"])
        self.assertFalse(data["leads"][0]["supports_pricing"])

    def test_forged_confidence_effective_dates_and_comparison_promotion_fail(self):
        original = load()
        for change in [dict(confidence="provider_reported"), dict(comparison_eligible=True), dict(reported_effective_date="2024-10-21"), dict(conflicts_with=[])]:
            data = copy.deepcopy(original)
            data["claims"][0].update(change)
            with self.assertRaises(ValueError):
                validate(data, {"xai", "nebius", "azure", "oracle"})

    def test_source_corruption_and_unretrieved_social_price_claims_fail(self):
        data = copy.deepcopy(load()); data["sources"][0]["excerpt"] += " modified"
        with self.assertRaisesRegex(ValueError, "hash differs"):
            validate(data, {"xai", "nebius", "azure", "oracle"})
        data = copy.deepcopy(load()); data["leads"][0]["supports_pricing"] = True
        with self.assertRaisesRegex(ValueError, "cannot corroborate"):
            validate(data, {"xai", "nebius", "azure", "oracle"})

    def test_unknown_or_dynamic_catalog_prices_do_not_become_zero_prices(self):
        for pricing in [{"prompt": "-1", "completion": None}, {"context_length": 10000}, {"discount": 50}, None]:
            row = dict(assertion_type="historical_native_model", source_record=dict(pricing=pricing))
            self.assertIsNone(price_evidence(row))
        row["source_record"]["pricing"] = dict(prompt="0.000001", completion="0")
        self.assertEqual(price_evidence(row), "structured_native")

    def test_document_candidates_need_aligned_price_columns_not_dates_or_context(self):
        def row(headers, cells, aligned=True):
            return dict(assertion_type="historical_document_row", identity_scope={}, source_record=dict(
                alignment_verified=aligned, headers=[dict(text=h) for h in headers], cells=[dict(text=c) for c in cells]))
        self.assertIsNone(price_evidence(row(["Model", "Context tokens"], ["model-12", "128000"])))
        self.assertIsNone(price_evidence(row(["Model", "Shutdown date"], ["model", "2024-12-12"])))
        self.assertIsNone(price_evidence(row(["Model", "Input price / 1M tokens"], ["model", "-"])))
        self.assertIsNone(price_evidence(row(["Model", "Input price / 1M tokens"], ["model", "$1"], False)))
        self.assertEqual(price_evidence(row(["Model", "Input price / 1M tokens"], ["model", "$1.25"])), "document_price_candidate")

    def test_ovh_nested_native_prices_are_counted_without_using_performance_or_currency(self):
        row = dict(provider="ovhcloud", assertion_type="historical_native_model", source_record=dict(metadata=dict(
            usage_information=dict(avg_throughtput=2, pricing=[dict(price="0.09", price_unit="million_input_tokens")]))))
        self.assertEqual(price_evidence(row), "structured_native")
        row["source_record"]["metadata"]["usage_information"]["pricing"] = []
        self.assertIsNone(price_evidence(row))

    def test_successful_recovery_resolves_target_without_erasing_earlier_lookup_check(self):
        descriptors = batch("groq", b'<p>Historical model evidence</p>')
        meta = descriptors[1]["metadata"]
        check = dict(kind="coverage", capture_id=None, provider="groq", profile=PROFILE,
            provenance="historical_discovery_v2", source_url=meta["replay_url"], target_url=meta["source_url"],
            checked_at="2026-10-26T10:00:00Z", state="budget_deferred", http_status=None, transport_exit_code=None,
            archive_capture_at=meta["archive_capture_at"], archive_digest=meta["archive_digest"], index_label="index", comparison_eligible=False)
        with tempfile.TemporaryDirectory() as directory, patch("scripts.historical_price_coverage.load", return_value={"claims": []}):
            root = Path(directory)
            ingest(root, descriptors[:1], checks=[check])
            self.assertEqual(build(root)["providers"]["groq"]["outstanding_replay_targets"], 1)
            ingest(root, descriptors)
            result = build(root)["providers"]["groq"]
            self.assertEqual(result["outstanding_replay_targets"], 0)
            self.assertEqual(result["retained_lookup_checks"], {"budget_deferred": 1})


if __name__ == "__main__":
    unittest.main()
