"""Offline fixtures exercise optional API paths; these are not real observations."""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from providers import fireworks, google_billing, groq, together, vertex
from providers.common import _NoCredentialRedirect, fetch_text
from providers.pricing_api import fetch_pages
from scripts.collect import read_history, run
from scripts.normalize import catalog, normalize
from scripts.provider_inventory import prepare_source

FIXTURES = Path(__file__).parent / "fixtures"
TIME = "2026-10-03T12:00:00Z"


class PricingAPITests(unittest.TestCase):
    def setUp(self):
        _, self.aliases = catalog()
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def fixture(self, name):
        return (FIXTURES / name).read_text()

    def test_together_api_token_prices_cache_zero_and_missing_cache(self):
        result = together.parse_api(self.fixture("together-api.json"), self.aliases)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0]["input_per_million"], 0.15)
        self.assertEqual(result.records[0]["cache_read_per_million"], 0)
        self.assertIsNone(result.records[1]["cache_read_per_million"])
        self.assertIsNone(result.records[0]["quantization"])
        self.assertEqual(result.source_kind, "api")
        self.assertFalse(result.authoritative_catalog)
        for row in result.records:
            normalize(row, self.aliases, TIME, result.source_sha256)

    def test_together_missing_invalid_rates_or_wrong_modality_fail_closed(self):
        fixture = json.loads(self.fixture("together-api.json"))
        mutations = [dict(pricing={"input": 0.15}), dict(pricing={"input": -1, "output": 1}),
                     dict(pricing={"input": "nan", "output": 1}), dict(type="audio")]
        for mutation in mutations:
            models = copy.deepcopy(fixture)
            models[0].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError)):
                together.parse_api(json.dumps(models), self.aliases)

    def test_together_uses_auth_header_and_retains_all_modalities(self):
        os.environ["TOGETHER_API_KEY"] = "fixture-secret"
        body = self.fixture("together-api.json")
        with patch("providers.together.fetch_text", return_value=body) as fetch:
            result = together.collect(self.aliases)
        fetch.assert_called_once_with(together.API_URL, headers={"Authorization": "Bearer fixture-secret"})
        self.assertEqual(len(json.loads(result.source_payload)), 3)
        self.assertNotIn("fixture-secret", result.source_payload)
        self.assertNotIn("fixture-secret", " ".join(result.source_urls))
        self.assertIsNone(result.fallback_reason)

    def test_missing_keys_use_explicit_documentation_fallbacks(self):
        for provider, fixture, key in [(together, "together.md", "TOGETHER_API_KEY"),
                                       (fireworks, "fireworks.md", "FIREWORKS_API_KEY"),
                                       (vertex, "vertex.html", "GOOGLE_CLOUD_BILLING_API_KEY")]:
            with self.subTest(provider=provider.__name__), patch.object(provider, "fetch_text", return_value=self.fixture(fixture)):
                result = provider.collect(self.aliases)
                self.assertEqual(result.source_kind, "documentation")
                self.assertIn(key, result.fallback_reason)
                self.assertIsNone(result.parse_error)

    def test_api_failure_fallback_reason_redacts_key(self):
        os.environ["TOGETHER_API_KEY"] = "fixture-secret"
        with patch("providers.together.fetch_text", side_effect=[RuntimeError("rejected fixture-secret"), self.fixture("together.md")]):
            result = together.collect(self.aliases)
        self.assertEqual(result.source_kind, "documentation")
        self.assertIn("unavailable", result.fallback_reason)
        self.assertNotIn("fixture-secret", result.fallback_reason)

    def test_fetched_api_parse_failure_is_archived_not_overwritten_with_docs(self):
        os.environ["TOGETHER_API_KEY"] = "fixture-secret"
        body = '[{"id":"openai/gpt-oss-120b","type":"chat","pricing":{"new_rate":5}}]'
        with patch("providers.together.fetch_text", return_value=body) as fetch:
            result = together.collect(self.aliases)
        fetch.assert_called_once()
        self.assertEqual(result.source_payload, body)
        self.assertEqual(result.source_kind, "api")
        self.assertTrue(result.parse_error)
        self.assertFalse(result.records)

    def test_fireworks_per_mode_prices_and_unsupported_modalities_stay_raw(self):
        body = self.fixture("fireworks-api.json")
        result = fireworks.parse_api(body, self.aliases)
        self.assertEqual([r["service_tier"] for r in result.records], ["standard", "priority"])
        self.assertEqual(result.records[0]["cache_read_per_million"], 0.015)
        self.assertIsNone(result.records[1]["cache_read_per_million"])
        self.assertEqual(result.records[1]["output_per_million"], 1.2)
        self.assertEqual(len(json.loads(result.source_payload)["data"]), 4)
        self.assertFalse(result.authoritative_catalog)
        for row in result.records:
            normalize(row, self.aliases, TIME, result.source_sha256)

    def test_full_fireworks_collection_accepts_an_unpriced_untracked_product(self):
        os.environ["FIREWORKS_API_KEY"]="fixture-secret"
        payload=json.loads(self.fixture("fireworks-api.json"))
        payload["data"].append(dict(id="accounts/fireworks/models/fixture-router",kind="router",pricing_mode="per-selected-model"))
        with tempfile.TemporaryDirectory() as directory,patch("providers.fireworks.fetch_pages",return_value=(payload,[fireworks.API_URL])):
            path=Path(directory)
            self.assertEqual(run(path,["fireworks"],strict=True),0)
            index=json.loads((path/"provider_inventory.json").read_text())["providers"][0]
            self.assertEqual(index["source_kind"],"api")
            self.assertEqual(index["record_count"],5)
            native=json.loads((path/index["latest_path"]).read_text())["records"]
            router=next(r for r in native if r["native_id"].endswith("fixture-router"))
            self.assertEqual(router["rates"],[])
            self.assertEqual(json.loads((path/"status.json").read_text())["providers"][0]["state"],"ok")
            self.assertEqual(len(read_history(path/"price_history.csv")),2)

    def test_fireworks_unknown_units_currency_mode_and_missing_prices_fail_closed(self):
        base = json.loads(self.fixture("fireworks-api.json"))
        for kind in ("unit", "currency", "amount", "mode", "missing", "duplicates"):
            payload = copy.deepcopy(base)
            model = payload["data"][0]
            if kind == "unit":
                model["pricing"][0]["unit"] = "1K tokens"
            elif kind == "currency":
                model["pricing"][0]["amount"] = {"currencyCode": "EUR", "units": "1"}
            elif kind == "amount":
                model["pricing"][0]["amount"] = None
            elif kind == "mode":
                model["serverless_mode"] = "unknown-new-mode"
            elif kind == "missing":
                model["pricing"].pop()
            else:
                model["pricing"].append(model["pricing"][0])
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                fireworks.parse_api(json.dumps(payload), self.aliases)

    def test_fireworks_pagination_no_coding_filter_and_full_raw_inventory(self):
        os.environ["FIREWORKS_API_KEY"] = "fixture-secret"
        fixture = json.loads(self.fixture("fireworks-api.json"))
        first = dict(data=fixture["data"][:2], nextPageToken="page-two", fixture_metadata="retained")
        second = dict(data=fixture["data"][2:], next_page_token="")
        with patch("providers.pricing_api.fetch_text", side_effect=[json.dumps(first), json.dumps(second)]) as fetch:
            result = fireworks.collect(self.aliases)
        self.assertEqual(result.source_kind, "api")
        self.assertEqual(len(json.loads(result.source_payload)["data"]), 4)
        self.assertEqual(json.loads(result.source_payload)["page_metadata"][0]["fixture_metadata"], "retained")
        self.assertEqual(len(result.source_urls), 2)
        for call in fetch.call_args_list:
            self.assertNotIn("use_cases", call.args[0])
            self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer fixture-secret")
        self.assertEqual(parse_qs(urlparse(result.source_urls[1]).query)["pageToken"], ["page-two"])

    def test_fireworks_fetch_failure_falls_back_but_pricing_parse_failure_does_not(self):
        os.environ["FIREWORKS_API_KEY"] = "fixture-secret"
        with patch("providers.fireworks.fetch_pages", side_effect=RuntimeError("rejected fixture-secret")), patch("providers.fireworks.fetch_text", return_value=self.fixture("fireworks.md")):
            result = fireworks.collect(self.aliases)
        self.assertEqual(result.source_kind, "documentation")
        self.assertNotIn("fixture-secret", result.fallback_reason)
        payload = json.loads(self.fixture("fireworks-api.json"))
        payload["data"][0]["pricing"] = []
        with patch("providers.fireworks.fetch_pages", return_value=(payload, [fireworks.API_URL])), patch("providers.fireworks.fetch_text") as document:
            result = fireworks.collect(self.aliases)
        document.assert_not_called()
        self.assertEqual(result.source_kind, "api")
        self.assertTrue(result.parse_error)
        self.assertEqual(json.loads(result.source_payload)["data"][0]["pricing"], [])

    def test_api_pagination_rejects_cycles_bad_tokens_incomplete_pages_and_overflow(self):
        for responses, limit in [([{"data": [{}], "nextPageToken": "repeat"}] * 2, 100),
                                 ([{"data": [{}], "nextPageToken": 42}], 100),
                                 ([{"data": [{}], "nextPageToken": "a", "next_page_token": "b"}], 100),
                                 ([{"error": "not a catalog"}], 100),
                                 ([{"data": [{}], "nextPageToken": "a"}], 1)]:
            with self.subTest(responses=responses), patch("providers.pricing_api.fetch_text", side_effect=[json.dumps(x) for x in responses]):
                with self.assertRaises(ValueError):
                    fetch_pages(fireworks.API_URL, "data", {"Authorization": "Bearer key"},
                                token_keys=("nextPageToken", "next_page_token"), max_pages=limit)

    def test_pagination_treats_url_like_tokens_as_data_not_redirect_targets(self):
        token = "https://evil.example/?key=not-an-api-key"
        pages = [dict(data=[{}], nextPageToken=token), dict(data=[{}])]
        with patch("providers.pricing_api.fetch_text", side_effect=[json.dumps(p) for p in pages]) as fetch:
            _, urls = fetch_pages(fireworks.API_URL, "data", {"Authorization": "Bearer key"})
        self.assertEqual(urlparse(urls[1]).hostname, "api.fireworks.ai")
        self.assertEqual(parse_qs(urlparse(urls[1]).query)["pageToken"], [token])
        self.assertEqual(fetch.call_count, 2)

    def vertex_catalog_fixture(self):
        service = dict(name="services/FIXTURE-SERVICE", displayName="Vertex AI")
        sku = dict(name=service["name"] + "/skus/FIXTURE-TOKEN", description="Fixture USD tokens",
                   serviceRegions=["global"], pricingInfo=[dict(effectiveTime=TIME, pricingExpression=dict(
                       usageUnit="1k", baseUnit="token", baseUnitConversionFactor=1000,
                       tieredRates=[dict(startUsageAmount=0, unitPrice=dict(currencyCode="USD", units="0", nanos=750000))]))])
        return service, dict(skus=[sku], page_count=1, page_metadata=[{}])

    def test_google_discovers_vertex_and_preserves_original_sku_price_units(self):
        service, sku_page = self.vertex_catalog_fixture()
        services = dict(services=[dict(name="services/OTHER", displayName="Other"), service])
        with patch("providers.pricing_api.fetch_text", side_effect=[json.dumps(services), json.dumps(sku_page)]) as fetch:
            payload, urls, sku_url = google_billing.vertex_catalog("fixture-secret")
        self.assertEqual(payload["catalog"]["skus"], sku_page["skus"])
        self.assertIn("currencyCode=USD", sku_url)
        self.assertEqual(len(urls), 2)
        self.assertNotIn("fixture-secret", " ".join(urls))
        for call in fetch.call_args_list:
            self.assertEqual(call.kwargs["headers"], {"X-Goog-Api-Key": "fixture-secret"})

    def test_google_refuses_ambiguous_service_or_foreign_skus(self):
        service, skus = self.vertex_catalog_fixture()
        for pages in [[dict(services=[service, service])],
                      [dict(services=[service]), dict(skus=[dict(name="services/OTHER/skus/WRONG")])]]:
            with self.subTest(pages=pages), patch("providers.pricing_api.fetch_text", side_effect=[json.dumps(p) for p in pages]):
                with self.assertRaises(ValueError):
                    google_billing.vertex_catalog("fixture-secret")

    def test_vertex_combined_inventory_keeps_api_skus_and_reviewed_document_quotes(self):
        os.environ["GOOGLE_CLOUD_BILLING_API_KEY"] = "fixture-secret"
        service, skus = self.vertex_catalog_fixture()
        api_payload = dict(service=service, catalog=skus, currency="USD")
        urls = ["https://cloudbilling.googleapis.com/v1/services/FIXTURE-SERVICE/skus"]
        with patch("providers.vertex.vertex_catalog", return_value=(api_payload, urls, urls[0])), patch("providers.vertex.fetch_text", return_value=self.fixture("vertex.html")):
            result = vertex.collect(self.aliases)
        self.assertEqual(result.source_kind, "api+documentation")
        self.assertEqual(len(result.records), 15)
        self.assertTrue(all(r["source_url"] == vertex.SOURCE for r in result.records))
        payload = json.loads(result.source_payload)
        self.assertEqual(payload["cloud_billing_catalog"]["catalog"]["skus"], skus["skus"])
        with tempfile.TemporaryDirectory() as directory:
            row, artifact = prepare_source("vertex", "Vertex AI", result, TIME, Path(directory), {})
        self.assertEqual(row["payload_record_count"], 1)
        self.assertGreater(artifact["table_count"], 0)
        self.assertEqual(hashlib.sha256(result.source_payload.encode()).hexdigest(), result.source_sha256)

    def test_vertex_api_fetch_failure_has_an_explicit_redacted_fallback(self):
        os.environ["GOOGLE_CLOUD_BILLING_API_KEY"] = "fixture-secret"
        with patch("providers.vertex.vertex_catalog", side_effect=RuntimeError("rejected fixture-secret")), patch("providers.vertex.fetch_text", return_value=self.fixture("vertex.html")):
            result = vertex.collect(self.aliases)
        self.assertEqual(result.source_kind, "documentation")
        self.assertIn("catalog API unavailable", result.fallback_reason)
        self.assertNotIn("fixture-secret", result.fallback_reason)

    def test_vertex_document_failure_does_not_discard_successful_api_inventory(self):
        os.environ["GOOGLE_CLOUD_BILLING_API_KEY"] = "fixture-secret"
        service, skus = self.vertex_catalog_fixture()
        urls = ["https://cloudbilling.googleapis.com/v1/services/FIXTURE-SERVICE/skus"]
        with patch("providers.vertex.vertex_catalog", return_value=(dict(service=service, catalog=skus), urls, urls[0])), patch("providers.vertex.fetch_text", side_effect=RuntimeError("unavailable")):
            result = vertex.collect(self.aliases)
        self.assertTrue(result.parse_error)
        self.assertFalse(result.records)
        self.assertIn("cloud_billing_catalog", json.loads(result.source_payload))

    def test_groq_machine_readable_markdown_exact_ids_and_contact_sales_exclusion(self):
        result = groq.parse_markdown(self.fixture("groq.md"), self.aliases)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["provider_model_id"], "openai/gpt-oss-120b")
        self.assertEqual(result.records[0]["output_per_million"], 0.6)
        with patch("providers.groq.fetch_text", return_value=self.fixture("groq.md")) as fetch:
            result = groq.collect(self.aliases)
        fetch.assert_called_once_with(groq.FETCH_URL)
        self.assertEqual(result.source_kind, "documentation")

    def test_authenticated_fetch_rejects_redirects_http_and_redacts_bearer_key(self):
        self.assertIsNone(_NoCredentialRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example"))
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            fetch_text("http://api.example", headers={"Authorization": "Bearer fixture-secret"})
        opener = Mock()
        opener.open.side_effect = RuntimeError("fixture-secret was rejected")
        with patch("providers.common.build_opener", return_value=opener), patch("providers.common.time.sleep"):
            with self.assertRaises(RuntimeError) as error:
                fetch_text(together.API_URL, headers={"Authorization": "Bearer fixture-secret"})
        self.assertNotIn("fixture-secret", str(error.exception))
        self.assertIn("[redacted]", str(error.exception))

    def test_api_parse_failure_preserves_history_and_source_strategy_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch("providers.together.fetch_text", return_value=self.fixture("together.md")), patch("scripts.collect.utc_now", return_value=TIME):
                self.assertEqual(run(path, ["together"]), 0)
            first_status = json.loads((path / "status.json").read_text())["providers"][0]
            first_index = json.loads((path / "provider_inventory.json").read_text())["providers"][0]
            self.assertEqual(first_status["source_kind"], "documentation")
            self.assertEqual(first_status["fallback_reason"], first_index["fallback_reason"])
            self.assertIn("TOGETHER_API_KEY", first_status["fallback_reason"])
            history = (path / "price_history.csv").read_bytes()
            latest = (path / "latest_prices.json").read_bytes()
            os.environ["TOGETHER_API_KEY"] = "fixture-secret"
            invalid = '[{"id":"openai/gpt-oss-120b","type":"chat","pricing":{}}]'
            with patch("providers.together.fetch_text", return_value=invalid), patch("scripts.collect.utc_now", return_value="2026-10-04T12:00:00Z"):
                self.assertEqual(run(path, ["together"], strict=True), 1)
            self.assertEqual(history, (path / "price_history.csv").read_bytes())
            self.assertEqual(latest, (path / "latest_prices.json").read_bytes())
            index = json.loads((path / "provider_inventory.json").read_text())["providers"][0]
            status = json.loads((path / "status.json").read_text())["providers"][0]
            self.assertEqual(index["source_kind"], "documentation")  # last good full catalog
            self.assertEqual(index["last_attempt_state"], "error")
            self.assertEqual(status["source_kind"], "api")
            self.assertEqual(status["state"], "error")
            self.assertTrue((path / index["latest_path"]).exists())


if __name__ == "__main__":
    unittest.main()
