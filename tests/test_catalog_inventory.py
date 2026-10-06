import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.common import Collection
from scripts.archive_reference import lookup_reference
from scripts.catalog_inventory import normalize_inventory
from scripts.collect import run
from scripts.inventory_storage import prepare_catalog, history_content
from scripts.normalize import catalog
from providers import together

FIXTURES = Path(__file__).parent / "fixtures"
TIME = "2026-10-06T06:17:00Z"


def result(body, kind="documentation", source="https://example.com/pricing"):
    return Collection([], source, hashlib.sha256(body.encode()).hexdigest(), source_payload=body,
                      source_urls=[source], source_kind=kind)


def doc(price="1.00"):
    return "# Model pricing\n\n| Model | Input price / 1M tokens |\n|---|---|\n| A | $" + price + " |\n"


class FullInventoryTests(unittest.TestCase):
    def test_all_document_providers_and_modalities_are_not_alias_filtered(self):
        for provider, extension in [("openai", "md"), ("anthropic", "md"), ("gemini", "md"),
                                    ("vertex", "html"), ("together", "md"), ("fireworks", "md"), ("groq", "md")]:
            body = (FIXTURES / (provider + "." + extension)).read_text()
            with self.subTest(provider=provider):
                inventory, fingerprint = normalize_inventory(provider, body, "documentation")
                self.assertTrue(inventory["records"])
                self.assertEqual(len(fingerprint), 64)
                self.assertTrue(all(not r["comparison_eligible"] for r in inventory["records"]))
        # Image/audio formulas do not become fabricated token costs.
        inventory, _ = normalize_inventory("test", "| Product | Price |\n|---|---|\n| Image model | $0.01 per image |\n| Speech model | $0.20 per minute |\n", "documentation")
        self.assertEqual(len(inventory["records"]), 2)
        self.assertEqual({r["rates"][0]["amount"] for r in inventory["records"]}, {"0.01", "0.2"})
        self.assertTrue(all(r["rates"][0]["conditions"]["unit_verified"] for r in inventory["records"]))

    def test_model_order_json_formatting_and_key_order_do_not_create_versions(self):
        models = [dict(model_name="untracked/image", type="text-to-image", pricing=dict(type="image_units", cents_per_image_unit=1)),
                  dict(model_name="untracked/audio", type="text-to-speech", pricing=dict(type="output_length", cents_per_output_sec=0.1))]
        a, h1 = normalize_inventory("deepinfra", json.dumps(models), "api")
        b, h2 = normalize_inventory("deepinfra", json.dumps(models[::-1], sort_keys=True, indent=4), "api")
        self.assertEqual(a, b)
        self.assertEqual(h1, h2)
        self.assertEqual(a["records"][0]["rates"][0]["currency"], "USD")

    def test_deepinfra_multipliers_conditions_and_image_units_are_preserved(self):
        pricing = dict(type="image_units", cents_per_image_unit=1, default_width=1024, default_height=1024,
                       rate_per_service_tier_priority=1.5, full="$0.01 per provider unit, not per image")
        inventory, _ = normalize_inventory("deepinfra", json.dumps([dict(model_name="image", pricing=pricing)]), "api")
        row = inventory["records"][0]
        self.assertEqual(row["billing"]["rules"], pricing)
        self.assertEqual(row["rates"][0]["amount"], "0.01")
        self.assertEqual(row["rates"][0]["unit"], "provider image unit")
        self.assertFalse(row["comparison_eligible"])

    def test_novita_native_integer_values_are_not_dollars_or_free(self):
        body = json.dumps(dict(data=[dict(id="unpriced", input_token_price_per_m=0, output_token_price_per_m=10000)]))
        inventory, _ = normalize_inventory("novita", body, "api")
        row = inventory["records"][0]
        self.assertEqual(row["rates"], [])
        self.assertEqual(row["billing"]["rules"]["native_output_billing_units"], 10000)

    def test_novita_prompt_bands_and_multimodal_native_units_are_preserved(self):
        bands = [dict(min_tokens=1, max_tokens=524288, pricing=dict(prompt=dict(price_per_m_decimal="0.3"))),
                 dict(min_tokens=524288, max_tokens=1000000, pricing=dict(prompt=dict(price_per_m_decimal="0.6")))]
        pricing = dict(prompt=dict(price_per_m_decimal="0.3"),multimodal_input=[dict(modals=["audio"],input_token_base_price=3000)])
        body=json.dumps(dict(data=[dict(id="multimodal",pricing=pricing,is_tiered_billing=True,tiered_billing_configs=bands)]))
        inventory,_=normalize_inventory("novita",body,"api");row=inventory["records"][0]
        self.assertEqual(row["billing"]["rules"]["tiered_billing_configs"],bands)
        self.assertEqual(row["billing"]["rules"]["rules"]["multimodal_input"],pricing["multimodal_input"])
        self.assertEqual([r["amount"] for r in row["rates"]],["0.3","0.3","0.6"])
        self.assertEqual(row["rates"][-1]["conditions"]["source_tier_bounds"]["max_tokens"],1000000)

    def test_together_nontext_amounts_are_decimal_but_have_no_invented_text_unit(self):
        body=json.dumps([dict(id="image",type="image",pricing=dict(base=0.004,finetune=0.008))])
        inventory,_=normalize_inventory("together",body,"api");rates=inventory["records"][0]["rates"]
        self.assertEqual([r["amount"] for r in rates],["0.004","0.008"])
        self.assertTrue(all(r["unit"] is None and not r["conditions"]["unit_verified"] for r in rates))

    def test_azure_and_bedrock_preserve_all_native_meters_dimensions_and_units(self):
        for provider in ("azure", "bedrock"):
            body = (FIXTURES / (provider + ".json")).read_text()
            inventory, _ = normalize_inventory(provider, body, "api")
            self.assertTrue(inventory["records"])
            self.assertTrue(all(r["rates"] for r in inventory["records"]))
            self.assertTrue(all(r["rates"][0]["unit"] for r in inventory["records"]))

    def test_authenticated_models_are_not_filtered_to_text_or_curated_ids(self):
        for provider in ("together", "fireworks"):
            inventory, _ = normalize_inventory(provider, (FIXTURES / (provider + "-api.json")).read_text(), "api")
            self.assertGreaterEqual(len(inventory["records"]), 3)
            self.assertTrue(any("fixture" in r["native_id"] for r in inventory["records"]))

    def test_fireworks_unpriced_catalog_rows_remain_unknown_not_free(self):
        for pricing in ("missing", None, []):
            model=dict(id="accounts/fireworks/models/fixture-router",kind="router",pricing_mode="per-selected-model",aliases=["fixture-router"],use_cases=["routing"])
            if pricing != "missing":model["pricing"]=pricing
            inventory,_=normalize_inventory("fireworks",json.dumps(dict(data=[model])),"api")
            row=inventory["records"][0]
            self.assertEqual(row["rates"],[])
            self.assertEqual(row["billing"]["state"],"source_native_or_unpriced")
            self.assertEqual(row["metadata"]["pricing_mode"],"per-selected-model")
            self.assertEqual(row["metadata"]["kind"],"router")
            self.assertFalse(row["comparison_eligible"])
        for invalid in ({"input":1},"1",False):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                normalize_inventory("fireworks",json.dumps(dict(data=[dict(id="model",pricing=invalid)])),"api")

    def test_fireworks_sku_reordering_does_not_create_price_history(self):
        payload=json.loads((FIXTURES/"fireworks-api.json").read_text())
        _,before=normalize_inventory("fireworks",json.dumps(payload),"api")
        for row in payload["data"]:row["pricing"].reverse()
        _,after=normalize_inventory("fireworks",json.dumps(payload),"api")
        self.assertEqual(before,after)

    def test_google_sku_pricing_info_is_retained_with_original_conversion_rules(self):
        info = dict(effectiveTime=TIME, pricingExpression=dict(usageUnit="1k", baseUnit="token", baseUnitConversionFactor=1000,
                    tieredRates=[dict(startUsageAmount=0, unitPrice=dict(currencyCode="USD", units="0", nanos=750000))]))
        payload = dict(cloud_billing_catalog=dict(service=dict(name="services/FIXTURE"), catalog=dict(skus=[dict(name="services/FIXTURE/skus/ID", pricingInfo=[info])])),
                       curated_pricing_document=dict(body=doc()))
        inventory, _ = normalize_inventory("vertex", json.dumps(payload), "api+documentation")
        sku = next(r for r in inventory["records"] if r["kind"] == "sku")
        self.assertEqual(sku["billing"]["pricing_info"], [info])
        self.assertEqual(sku["rates"][0]["amount"], "0.00075")
        self.assertEqual(sku["rates"][0]["unit"], "1k")
        self.assertEqual(len(inventory["records"]), 2)

    def test_structured_money_rejects_invalid_currency_fractional_units_and_nanos(self):
        for money in [dict(currencyCode="USD",units="1.1"),dict(currencyCode="USD",units="2",nanos=-1),
                      dict(currencyCode="USD",nanos=1000000000),dict(currencyCode="USD",nanos=True),
                      dict(currencyCode="usd",units="1"),dict(units="1")]:
            body=json.dumps(dict(data=[dict(id="model",serverless_mode="standard",pricing=[dict(sku="input",unit="1M tokens",amount=money)])]))
            with self.subTest(money=money),self.assertRaises(ValueError):
                normalize_inventory("fireworks",body,"api")

    def test_pricing_unit_conditions_and_prose_changes_are_not_lost(self):
        _, original = normalize_inventory("test", doc(), "documentation")
        for changed in [doc("2.00"), doc().replace("1M tokens", "1K tokens"), doc() + "Price applies only below 200K tokens.\n"]:
            _, changed_hash = normalize_inventory("test", changed, "documentation")
            self.assertNotEqual(original, changed_hash)

    def test_html_script_noise_does_not_change_pricing_fingerprint(self):
        body = '<html><h2>Image prices</h2><table><tr><th>Model</th><th>Price/image</th></tr><tr><td>A</td><td>$1.00</td></tr></table><script>nonce=123</script></html>'
        self.assertEqual(normalize_inventory("test", body, "documentation"), normalize_inventory("test", body.replace("nonce=123", "nonce=456"), "documentation"))

    def test_document_heading_hierarchy_and_per_component_units_are_preserved(self):
        body="## A\n| Model | Price |\n|---|---|\n| a | $0.10 per image + $0.20 per minute |\n## B\n| Model | Price |\n|---|---|\n| b | $0.30 |\n"
        inventory,_=normalize_inventory("test",body,"documentation")
        row=next(r for r in inventory["records"] if r["label"]=="a")
        self.assertEqual([r["unit"] for r in row["rates"]],["per image","per minute"])
        row=next(r for r in inventory["records"] if r["label"]=="b")
        self.assertEqual(row["scope"]["headings"],["B"])

    def test_nested_html_billing_conditions_are_not_lost(self):
        body='<h2>Prices</h2><ul><li>Prices over 200K tokens: <p>additional caching charges apply.</p>Minimum billed duration is one minute.</li></ul><table><tr><th>Model</th><th>Price</th></tr><tr><td>A</td><td>$1</td></tr></table>'
        inventory,_=normalize_inventory("test",body,"documentation")
        self.assertTrue(any("200K" in p and "one minute" in p for p in inventory["billing_notes"]))

    def test_private_data_invalid_money_and_empty_catalogs_fail_closed(self):
        invalid = [json.dumps([dict(model_name="private", private=True, pricing=dict(type="tokens", cents_per_input_token=1))]),
                   json.dumps([dict(model_name="invalid", pricing=dict(type="tokens", cents_per_input_token=-1))]), "[]"]
        for body in invalid:
            with self.assertRaises(ValueError):
                normalize_inventory("deepinfra", body, "api")

    def test_source_quote_identity_does_not_include_its_price(self):
        a, _ = normalize_inventory("test", doc("1.00"), "documentation")
        b, _ = normalize_inventory("test", doc("2.00"), "documentation")
        self.assertEqual(a["records"][0]["id"], b["records"][0]["id"])
        self.assertNotEqual(a["records"][0]["billing"], b["records"][0]["billing"])


class InventoryRetentionTests(unittest.TestCase):
    def test_unchanged_checks_do_not_append_price_records_or_rewrite_catalogs(self):
        _, aliases = catalog()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            parsed = together.parse((FIXTURES / "together.md").read_text(), aliases)
            with patch("scripts.collect.together.collect", return_value=parsed), patch("scripts.collect.utc_now", return_value=TIME):
                self.assertEqual(run(path, ["together"]), 0)
            files = [path/"inventory_history.jsonl", path/"price_history.csv", path/"provider_catalogs/together.json"]
            before = [f.read_bytes() for f in files]
            with patch("scripts.collect.together.collect", return_value=parsed), patch("scripts.collect.utc_now", return_value="2026-10-07T06:17:00Z"):
                self.assertEqual(run(path, ["together"]), 0)
            self.assertEqual(before, [f.read_bytes() for f in files])
            self.assertEqual(len((path/"collection_checks.jsonl").read_text().splitlines()), 2)
            self.assertFalse((path/"provider_sources").exists())

    def test_revision_history_preserves_reverts_and_deduplicates_partial_write_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); index = {}; histories = ""
            for n, price in enumerate(["1", "2", "1"], 1):
                row, artifact, events = prepare_catalog("test", "Test", result(doc(price)), TIME, path, index)
                target=path/row["latest_path"]; target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(artifact))
                index["test"] = row
                history_path=path/"history.jsonl";history_path.write_text(histories)
                histories = history_content(history_path, events)
                history_path.write_text(histories)
                self.assertEqual(histories, history_content(history_path, events))
                self.assertEqual(row["revision"], n)
            events = [json.loads(line) for line in histories.splitlines()]
            self.assertEqual(sum(e["kind"] == "record_changed" for e in events), 2)
            self.assertEqual(len({e["id"] for e in events}), len(events))

    def test_existing_raw_archives_are_preserved_as_explicit_legacy_references(self):
        with tempfile.TemporaryDirectory() as directory:
            old = dict(id="test", latest_path="provider_sources/test/old.json", source_sha256="old", versions=[dict(path="old.json")], version_count=1)
            row, _, _ = prepare_catalog("test", "Test", result(doc()), TIME, Path(directory), {"test":old})
            self.assertEqual(row["legacy_source_archive"]["latest_path"], old["latest_path"])
            self.assertTrue(row["latest_path"].startswith("provider_catalogs/"))

    def test_new_raw_responses_are_gzipped_outside_permanent_storage(self):
        _, aliases = catalog()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);data=root/"data";raw=root/"temporary"
            parsed = together.parse((FIXTURES / "together.md").read_text(), aliases)
            with patch("scripts.collect.together.collect", return_value=parsed):
                self.assertEqual(run(data, ["together"], response_dir=raw), 0)
            self.assertTrue((raw/"together.source.gz").exists())
            self.assertFalse((data/"provider_sources").exists())

    def test_authenticated_raw_model_responses_are_not_uploaded(self):
        _, aliases = catalog()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); parsed=together.parse_api((FIXTURES/"together-api.json").read_text(),aliases)
            with patch("scripts.collect.together.collect",return_value=parsed):
                self.assertEqual(run(root/"data",["together"],response_dir=root/"temporary"),0)
            self.assertFalse((root/"temporary/together.source.gz").exists())


    def test_credential_echoes_are_rejected_before_any_source_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);key="actual-collector-secret";parsed=result(doc()+key)
            with patch.dict("os.environ",{"TOGETHER_API_KEY":key}),patch("scripts.collect.together.collect",return_value=parsed):
                self.assertEqual(run(root/"data",["together"],response_dir=root/"temporary"),1)
            self.assertFalse((root/"data/provider_catalogs/together.json").exists())
            self.assertFalse((root/"temporary/together.source.gz").exists())
            for file in (root/"data").rglob("*"):
                if file.is_file(): self.assertNotIn(key,file.read_text())

    def test_collector_error_messages_redact_credentials_in_saved_health(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);key="actual-collector-secret"
            with patch.dict("os.environ",{"TOGETHER_API_KEY":key}),patch("scripts.collect.together.collect",side_effect=ValueError("invalid "+key)):
                self.assertEqual(run(root,["together"]),1)
            self.assertNotIn(key,(root/"status.json").read_text())
            self.assertIn("[redacted]",(root/"status.json").read_text())


class ArchiveReferenceTests(unittest.TestCase):
    def test_verified_capture_must_match_exact_target_and_collector_bytes(self):
        r=result(doc());capture="20261006061700"
        api=dict(archived_snapshots=dict(closest=dict(available=True,status="200",timestamp=capture,url="https://web.archive.org/web/"+capture+"/"+r.source_url)))
        with patch("scripts.archive_reference._get",side_effect=[json.dumps(api).encode(),r.source_payload.encode()]):
            ref=lookup_reference(r,TIME)
        self.assertEqual(ref["state"],"verified")
        self.assertEqual(ref["capture_at"],TIME)

    def test_nearest_capture_is_not_accepted_without_content_verification(self):
        r=result(doc());capture="20260101000000"
        api=dict(archived_snapshots=dict(closest=dict(available=True,status="200",timestamp=capture,url="https://web.archive.org/web/"+capture+"/"+r.source_url)))
        with patch("scripts.archive_reference._get",side_effect=[json.dumps(api).encode(),doc("2").encode()]):
            self.assertEqual(lookup_reference(r,TIME)["state"],"content_mismatch")

    def test_archive_outages_and_missing_captures_are_nonblocking(self):
        with patch("scripts.archive_reference._get",side_effect=RuntimeError("unavailable")):
            self.assertEqual(lookup_reference(result(doc()),TIME)["state"],"unavailable")
        with patch("scripts.archive_reference._get",return_value=b'{"archived_snapshots":{}}'):
            self.assertEqual(lookup_reference(result(doc()),TIME)["state"],"unavailable")

    def test_credentials_and_api_responses_are_never_submitted_to_wayback(self):
        with patch("scripts.archive_reference._get") as request:
            self.assertEqual(lookup_reference(result("[]",kind="api"),TIME)["state"],"not_applicable")
            self.assertEqual(lookup_reference(result(doc(),source="https://example.com/pricing?key=secret"),TIME)["state"],"not_applicable")
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
