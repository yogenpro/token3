"""Broader historical evidence stays source-native, bounded and non-comparable."""
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

from scripts.historical_profiles import PROFILE, profiles, source_spec
from scripts.historical_sources import archive_time
from scripts.historical_ledger import ingest, read_ledger, record_discovery_failure
from scripts.discover_historical_evidence import Discovery, adopt_results, replay_receipt, replay_receipt_path, save, digest


def batch(provider, body, url=None):
    url = url or profiles()[provider]["sources"][0]["url"]
    stamp = "20240417000000"
    digest = base64.b32encode(hashlib.sha1(body).digest()).decode()
    query = "https://web.archive.org/cdx/search/cdx?" + urlencode(dict(url=url, matchType="exact", output="json", filter="statuscode:200",
        fl="timestamp,original,mimetype,statuscode,digest", limit="5001", to="20261026000000"))
    index = [["timestamp", "original", "mimetype", "statuscode", "digest"], [stamp, url, "application/octet-stream", "200", digest]]
    common = dict(provider=provider, retrieved_at="2026-10-26T10:00:00Z", source_published_at=None,
                  archive_capture_at=None, archive_digest=None, replay_url=None)
    return [dict(label="index", body=json.dumps(index).encode(), metadata=dict(common, source_kind="archive_index_v2", source_url=query,
                request_scope=dict(profile=PROFILE, target_url=url))),
            dict(label="capture", body=body, metadata=dict(common, source_kind="archived_native_v2", source_url=url,
                request_scope=dict(profile=PROFILE, index_label="index"), archive_capture_at=archive_time(stamp), archive_digest=digest,
                replay_url="https://web.archive.org/web/{}id_/{}".format(stamp, url)))]


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "ledger"

    def test_profiles_cover_tracked_providers_with_bedrock_native_versions(self):
        data = json.loads((Path(__file__).resolve().parents[1] / "data/provider_inventory.json").read_bytes())
        self.assertEqual(set(profiles()) | {"bedrock"}, {p["id"] for p in data["providers"]})
        self.assertEqual(len(profiles()), 25)
        for provider, profile in profiles().items():
            for source in profile["sources"]:
                self.assertEqual(source_spec(source["url"], provider), source)

    def test_auth_inference_and_cross_provider_sources_are_rejected(self):
        cases = [("together", "https://api.together.ai/v1/models"), ("fireworks", "https://api.fireworks.ai/v1/serverless/models"),
                 ("vertex", "https://cloudbilling.googleapis.com/v1/services/x/skus?key=fixture"),
                 ("openai", "https://api.openai.com/v1/responses"), ("openrouter", "https://openrouter.ai/api/v1/models?api_key=fixture"),
                 ("gemini", "https://platform.openai.com/docs/pricing"), ("azure", "https://prices.azure.com/api/retail/prices?$filter=other")]
        for provider, url in cases:
            with self.subTest(provider=provider, url=url), self.assertRaises(ValueError):
                source_spec(url, provider)

    def test_document_context_unknowns_and_identifier_column_survive(self):
        body = b'<html><h1>Regional pricing</h1><h2>Europe, long prompts</h2><p>Rate is in credits, not currency. Promotion ends next month.</p><table><tr><th>Model ID</th><th>Credits / 1M tokens</th></tr><tr><td>old/exact-2023</td><td>-</td></tr></table></html>'
        ingest(self.root, batch("databricks", body))
        _, rows = read_ledger(self.root)
        row = next(r for r in rows if r.get("assertion_type") == "historical_document_row")
        self.assertEqual(row["native_id"], "old/exact-2023")
        self.assertEqual(row["identity_scope"]["headings"], ["Regional pricing", "Europe, long prompts"])
        self.assertEqual(row["source_record"]["cells"][1]["text"], "-")
        self.assertFalse(row["comparison_eligible"])
        self.assertIsNone(row["source_reported_effective_at"])
        self.assertNotIn("rates", row)
        self.assertTrue(any("Promotion ends" in r.get("source_record", {}).get("text", "") for r in rows))

    def test_nested_tables_keep_text_and_explicitly_unparsed_table_state(self):
        body = b'<h1>Billing</h1><table><tr><td>Long prompts<table><tr><td>$2</td></tr></table></td></tr></table>'
        ingest(self.root, batch("anthropic", body))
        _, rows = read_ledger(self.root)
        self.assertFalse(any(r.get("assertion_type") == "historical_document_row" for r in rows))
        coverage = [r for r in rows if r["kind"] == "coverage"][-1]
        self.assertEqual(coverage["state"], "document_text_only_ambiguous_tables")

    def test_markdown_tabs_and_schedules_are_not_flattened_into_prices(self):
        body = b'# International\n<Tab title="Singapore">\nPeak 08:00-16:00 UTC, exceptions apply.\n| Model ID | Input |\n| --- | --- |\n| `model-v1` | 2 / peak; 1 / off-peak |\n</Tab>\n'
        ingest(self.root, batch("deepseek", body))
        _, rows = read_ledger(self.root)
        row = next(r for r in rows if r.get("assertion_type") == "historical_document_row")
        self.assertEqual(row["native_id"], "model-v1")
        self.assertEqual(row["source_record"]["cells"][1]["text"], "2 / peak; 1 / off-peak")
        self.assertTrue(any('Singapore' in r.get("source_record", {}).get("text", "") for r in rows))

    def test_native_gateway_prices_unknowns_and_sentinel_remain_unmodified(self):
        body = json.dumps(dict(data=[dict(id="past/model:exact", pricing=dict(prompt="-1", completion=None), architecture=dict(modality="text"))])).encode()
        ingest(self.root, batch("openrouter", gzip.compress(body, mtime=0)))
        _, rows = read_ledger(self.root)
        row = next(r for r in rows if r.get("assertion_type") == "historical_native_model")
        self.assertEqual(row["source_record"]["pricing"], dict(prompt="-1", completion=None))
        self.assertEqual(row["native_id"], "past/model:exact")
        self.assertEqual(row["identity_scope"], {})

    def test_huggingface_routes_remain_separate_and_unpriced(self):
        body = json.dumps(dict(data=[dict(id="creator/model", providers=[dict(provider="a", pricing=None), dict(provider="b", pricing=dict(input=1))])])).encode()
        ingest(self.root, batch("huggingface", body, "https://router.huggingface.co/v1/models"))
        _, rows = read_ledger(self.root)
        routes = [r for r in rows if r.get("assertion_type") == "historical_provider_route"]
        self.assertEqual({r["identity_scope"]["upstream_provider"] for r in routes}, {"a", "b"})
        self.assertIsNone(routes[0]["source_record"]["route"]["pricing"])

    def test_private_and_duplicate_model_ids_never_commit(self):
        for models in [[dict(id="a", private=True)], [dict(id="a"), dict(id="a")]]:
            with self.assertRaises(ValueError):
                ingest(self.root, batch("openrouter", json.dumps(dict(data=models)).encode()))
            self.assertFalse((self.root / "manifest.json").exists())

    def test_partial_catalog_is_not_successful_empty_catalog(self):
        body = json.dumps(dict(data=[dict(id="a")], has_more=True)).encode()
        ingest(self.root, batch("openrouter", body))
        manifest, rows = read_ledger(self.root)
        self.assertEqual(manifest["counts"]["assertion"], 0)
        self.assertEqual(rows[-1]["state"], "unparsed_or_incomplete_catalog")

    def test_malformed_pagination_does_not_assert_complete_catalog(self):
        body = json.dumps(dict(data=[dict(id="a")], links=["next-page"])).encode()
        ingest(self.root, batch("openrouter", body))
        manifest, rows = read_ledger(self.root)
        self.assertEqual(manifest["counts"]["assertion"], 0)
        self.assertEqual(rows[-1]["state"], "unparsed_or_incomplete_catalog")

    def test_private_or_malformed_routes_never_commit(self):
        for route in [None, dict(provider="a", private=True)]:
            body = json.dumps(dict(data=[dict(id="creator/model", providers=[route])])).encode()
            with self.assertRaises(ValueError):
                ingest(self.root, batch("huggingface", body, "https://router.huggingface.co/v1/models"))
            self.assertFalse((self.root / "manifest.json").exists())

    def test_failed_replay_check_requires_index_and_cannot_invent_response(self):
        descriptors = batch("groq", b'<h1>Prices</h1>')
        meta = descriptors[1]["metadata"]
        check = dict(kind="coverage", capture_id=None, provider="groq", profile=PROFILE,
            provenance="historical_discovery_v2", source_url=meta["replay_url"], target_url=meta["source_url"],
            checked_at="2026-10-26T10:00:00Z", state="transport_failed", http_status=None, transport_exit_code=7,
            archive_capture_at=meta["archive_capture_at"], archive_digest=meta["archive_digest"],
            index_label="index", comparison_eligible=False)
        ingest(self.root, descriptors[:1], checks=[check])
        before = (self.root / "manifest.json").read_bytes()
        manifest, rows = read_ledger(self.root)
        self.assertEqual(manifest["counts"]["capture"], 1)
        self.assertEqual(rows[-1]["state"], "transport_failed")
        self.assertIsNone(rows[-1]["capture_id"])
        self.assertEqual(ingest(self.root, descriptors[:1], checks=[check]), manifest)
        for changes in [dict(http_status=200), dict(archive_digest="A" * 32)]:
            with self.assertRaises(ValueError):
                ingest(self.root, descriptors[:1], checks=[dict(check, **changes)])
            self.assertEqual(before, (self.root / "manifest.json").read_bytes())
        # Legacy operator reports can still append/retry after v2 coverage.
        query = "https://web.archive.org/cdx/search/cdx?" + urlencode(dict(url="https://deepinfra.com/models", matchType="prefix",
            output="json", filter="statuscode:200", fl="timestamp,original,mimetype,statuscode,digest", limit="5001", to="20261026"))
        record_discovery_failure(self.root, query, "2026-10-26", 503, "2026-10-26T10:00:00Z")
        before = (self.root / "manifest.json").read_bytes()
        record_discovery_failure(self.root, query, "2026-10-26", 503, "2026-10-26T11:00:00Z")
        self.assertEqual(before, (self.root / "manifest.json").read_bytes())

    def test_external_transport_rejects_wrong_digest_and_path(self):
        stage = Path(self.temp.name) / "stage"
        (stage / "direct").mkdir(parents=True)
        body = b'<h1>Model history</h1>'
        descriptors = batch("groq", body)
        meta = descriptors[1]["metadata"]
        job = dict(provider="groq", stamp="20240417000000", url=meta["source_url"], digest=meta["archive_digest"], label="capture")
        (stage / "plan.json").write_text(json.dumps(dict(jobs=[job])))
        receipt = dict(index=0, http_status=200, exit_code=0, retrieved_at="2026-10-26T10:00:00Z", body_path="direct/body")
        (stage / "direct/body").write_bytes(b'wrong bytes')
        external = stage / "external.json"
        external.write_text(json.dumps([receipt]))
        self.assertEqual(adopt_results(stage, external), dict(digest_mismatch=1))
        external.write_text(json.dumps([dict(receipt, body_path="../outside")]))
        with self.assertRaises((ValueError, OSError)):
            adopt_results(stage, external)
        self.assertFalse(self.root.exists())

    def test_deferred_network_budget_does_not_make_request_or_capture(self):
        stage = Path(self.temp.name) / "stage"
        discovery = Discovery(stage, 0, 0)
        with patch("scripts.discover_historical_evidence.subprocess.run") as request:
            receipt = discovery.fetch("groq", "https://web.archive.org/cdx/search/cdx", "index")
        request.assert_not_called()
        self.assertEqual(receipt["state"], "budget_deferred")
        self.assertNotIn("retrieved_at", receipt)
        self.assertFalse(self.root.exists())

    def test_same_replay_timestamp_different_digests_have_independent_receipts(self):
        stage = Path(self.temp.name) / "stage"
        discovery = Discovery(stage, 0, 0)
        url = "https://web.archive.org/web/20240417000000id_/https://groq.com/pricing/"
        first, second = b'first archived body', b'second archived body'
        expected = [base64.b32encode(hashlib.sha1(raw).digest()).decode() for raw in (first, second)]
        body_path, body_sha = discovery.blob(first)
        legacy = dict(state="retrieved", body_path=body_path, body_sha256=body_sha, attempts=4)
        save(stage / 'requests' / (digest(('groq\n' + url).encode()) + '.json'), legacy)
        # A valid legacy receipt cannot satisfy another digest at this timestamp,
        # even when its retry count would otherwise stop requests.
        receipt = discovery.fetch('groq', url, 'second', expected=expected[1])
        self.assertEqual(receipt['state'], 'budget_deferred')
        self.assertEqual(replay_receipt(stage, 'groq', url, expected[0]), legacy)
        body_path, body_sha = discovery.blob(second)
        other = dict(state="retrieved", body_path=body_path, body_sha256=body_sha)
        save(replay_receipt_path(stage, 'groq', url, expected[1]), other)
        self.assertEqual(replay_receipt(stage, 'groq', url, expected[1]), other)
        self.assertEqual(replay_receipt(stage, 'groq', url, expected[0]), legacy)

    def test_pdf_page_text_is_not_an_aligned_rate_table(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        buffer = io.BytesIO()
        writer.write(buffer)
        ingest(self.root, batch("snowflake", buffer.getvalue()))
        _, rows = read_ledger(self.root)
        page = next(r for r in rows if r.get("assertion_type") == "historical_pdf_page")
        self.assertFalse(page["source_record"]["alignment_verified"])
        self.assertNotIn("currency", page)
        self.assertEqual(rows[-1]["state"], "pdf_text_only")

    def test_old_nebius_aria_table_retains_units_and_blank_identity_cells(self):
        from scripts.historical_price_coverage import price_evidence
        body = b'''<html><h1>AI Studio pricing</h1><p>Prices shown are per 1 million tokens.</p>
<div role="table"><div role="rowgroup"><div role="row"><div role="cell">Model</div><div role="cell">Flavor</div><div role="cell">Input</div><div role="cell">Output</div></div>
<div role="row"><div role="cell">Exact/old-model</div><div role="cell">fast</div><div role="cell">$0.03</div><div role="cell">$0.09</div></div>
<div role="row"><div role="cell"></div><div role="cell">base</div><div role="cell">$0.02</div><div role="cell">-</div></div></div></div></html>'''
        ingest(self.root, batch('nebius', body, 'https://nebius.com/prices-ai-studio'))
        _, rows = read_ledger(self.root)
        evidence = [r for r in rows if r.get('assertion_type') == 'historical_document_row']
        self.assertEqual(len(evidence), 2)
        self.assertEqual(evidence[1]['source_record']['cells'][0]['text'], '')
        self.assertEqual(evidence[1]['source_record']['cells'][3]['text'], '-')
        self.assertEqual(evidence[0]['source_record']['unit_context'], 'Prices shown are per 1 million tokens.')
        self.assertEqual(price_evidence(evidence[0]), 'document_price_candidate')
        self.assertFalse(evidence[0]['comparison_eligible'])

    def test_general_oracle_price_list_is_scoped_to_generative_ai(self):
        body = b'''<html><h1>OCI Price List</h1><h2>Compute</h2><table><tr><th>Product</th><th>Price</th></tr><tr><td>Compute SKU</td><td>1.20</td></tr></table>
<h2>Generative AI</h2><table><tr><th>Product</th><th>Price</th></tr><tr><td>Large Meta</td><td>0.015</td></tr></table></html>'''
        ingest(self.root, batch('oracle', body, 'https://www.oracle.com/cloud/price-list/'))
        _, rows = read_ledger(self.root)
        evidence = [r for r in rows if r.get('assertion_type') == 'historical_document_row']
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]['source_pointer'], dict(table=1, row=1))
        self.assertEqual(evidence[0]['source_record']['cells'][0]['text'], 'Large Meta')

    def test_oracle_api_preserves_sku_metric_currency_and_unpriced_values(self):
        from scripts.historical_projection import project
        from scripts.historical_price_coverage import price_evidence
        item = dict(partNumber='B108077', displayName='Historical model', metricName='10,000 Transactions',
                    serviceCategory='OCI Generative AI - Models', currencyCodeLocalizations=[dict(currencyCode='USD', prices=[dict(model='PAY_AS_YOU_GO', value='0.0156')])])
        body = json.dumps(dict(items=[dict(partNumber='compute', serviceCategory='Compute'), item])).encode()
        url = 'https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/?currencyCode=USD'
        ingest(self.root, batch('oracle', body, url))
        _, rows = read_ledger(self.root)
        evidence = next(r for r in rows if r.get('assertion_type') == 'historical_oracle_sku')
        self.assertEqual(evidence['native_id'], 'B108077')
        self.assertEqual(evidence['source_pointer'], ['items', 1])
        self.assertEqual(price_evidence(evidence), 'structured_native')
        public = project(self.root)['assertions'][0]
        self.assertEqual(public['evidence']['metricName'], '10,000 Transactions')
        self.assertEqual(public['evidence']['currencyCodeLocalizations'][0]['prices'][0]['value'], '0.0156')
        self.assertFalse(public['comparison_eligible'])
        with self.assertRaises(ValueError):
            ingest(Path(self.temp.name) / 'duplicate', batch('oracle', json.dumps(dict(items=[item, item])).encode(), url))

    def test_nebius_public_flavors_do_not_collapse_or_publish_throughput(self):
        from scripts.historical_projection import project
        flavors = [dict(model_id='exact/old', label=name, regions=[dict(name=region)], input_price_per_million_tokens='0.03',
                        output_price_per_million_tokens=None, tokens_per_second=123) for name, region in [('fast', 'eu'), ('cheap', 'us')]]
        body = json.dumps([dict(name='Old model', flavors=flavors, created_at='2024-01-01', quality=99)]).encode()
        url = 'https://tokenfactory.nebius.com/api/public/models_info'
        ingest(self.root, batch('nebius', body, url))
        evidence = project(self.root)['assertions']
        self.assertEqual(len(evidence), 2)
        self.assertEqual({r['identity_scope']['flavor'] for r in evidence}, {'fast', 'cheap'})
        self.assertTrue(all(r['native_id'] == 'exact/old' and not r['comparison_eligible'] for r in evidence))
        self.assertNotIn('tokens_per_second', json.dumps(evidence))
        self.assertNotIn('quality', json.dumps(evidence))
        self.assertIsNone(evidence[0]['source_reported_effective_at'])

    def test_empty_indexes_are_evidence_not_vendor_absence(self):
        descriptors = batch("azure", b'<p>retired model evidence</p>', "https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/retired-models")[:1]
        descriptors[0]["body"] = b'[]'
        ingest(self.root, descriptors)
        _, rows = read_ledger(self.root)
        self.assertEqual(rows[-1]["returned_entries"], 0)
        self.assertEqual(rows[-1]["state"], "index_only")
        self.assertNotIn("retired", rows[-1])

    def test_wrong_archive_digest_and_cross_source_index_fail(self):
        descriptors = batch("groq", b'<h1>Prices</h1>')
        descriptors[1]["metadata"]["archive_digest"] = "A" * 32
        with self.assertRaisesRegex(ValueError, "digest/index"):
            ingest(self.root, descriptors)
        self.assertFalse((self.root / "manifest.json").exists())

    def test_current_document_retrospective_dates_are_not_backdated(self):
        provider, url = "oracle", "https://docs.oracle.com/en-us/iaas/Content/generative-ai/deprecating-on-demand.htm"
        descriptor = dict(label="retrospective", body=b'<h1>Retired models</h1><p>Retired 2024-10-02</p>', metadata=dict(provider=provider,
            source_kind="public_document_v2", source_url=url, replay_url=None, retrieved_at="2026-10-26T10:00:00Z",
            source_published_at=None, archive_capture_at=None, archive_digest=None, request_scope=dict(profile=PROFILE, final_url=url)))
        ingest(self.root, [descriptor])
        _, rows = read_ledger(self.root)
        self.assertIsNone(rows[0]["archive_capture_at"])
        self.assertTrue(all(r.get("source_reported_effective_at") is None for r in rows))


if __name__ == "__main__":
    unittest.main()
