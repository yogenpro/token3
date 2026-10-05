import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers import deepinfra, fireworks, groq, novita, together
from providers.common import Collection, number, observation
from scripts.collect import apply_snapshot, read_history, run as collect_run
from scripts.detect_changes import event
from scripts.normalize import catalog, normalize

FIXTURES = Path(__file__).parent / "fixtures"
TIME = "2026-10-03T12:00:00Z"
HASH = "a" * 64
MODEL = "openai/gpt-oss-120b"


def run(*args, **kwargs):
    # Legacy archive migration/retention tests use their original source format.
    return collect_run(*args, archive_legacy=True, **kwargs)


def record(model_id=MODEL, provider="novita", input_price=0.05, output_price=0.25, **metadata):
    return observation(provider, model_id, input_price, output_price, "https://api.novita.ai/v3/openai/models", context_window=131072, **metadata)


def collection(records=None, authoritative=True, source_body='{"models":[]}', parse_error=None):
    digest = hashlib.sha256(source_body.encode("utf-8")).hexdigest()
    return Collection(records if records is not None else [record()], "https://api.novita.ai/v3/openai/models", digest, authoritative, source_body, parse_error)


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.models, self.aliases = catalog()

    def test_exact_aliases_do_not_merge_thinking_or_other_versions(self):
        self.assertEqual(self.aliases["meta-llama/Llama-3.3-70B-Instruct-Turbo"], "meta/llama-3.3-70b-instruct")
        self.assertNotIn("qwen/qwen3-235b-a22b-thinking-2507", self.aliases)
        self.assertNotIn("openai/gpt-oss-120b-special", self.aliases)

    def test_deepinfra_cents_per_token_and_precision(self):
        body = json.dumps([dict(model_name=MODEL, max_tokens=131072, quantization="bfloat16", pricing=dict(type="tokens", cents_per_input_token=0.0000037, cents_per_output_token=0.000017, rate_per_input_token_cached=0.5))])
        parsed = deepinfra.parse(body, self.aliases)
        self.assertAlmostEqual(parsed.records[0]["input_per_million"], 0.037)
        self.assertAlmostEqual(parsed.records[0]["output_per_million"], 0.17)
        self.assertAlmostEqual(parsed.records[0]["cache_read_per_million"], 0.0185)
        self.assertEqual(parsed.records[0]["quantization"], "bfloat16")
        self.assertTrue(parsed.authoritative_catalog)

    def test_deepinfra_tiers_remain_separate(self):
        body = json.dumps([dict(model_name=MODEL, max_tokens=131072, pricing=dict(type="tokens", cents_per_input_token=0.00001, cents_per_output_token=0.00003, rate_per_service_tier_priority=1.5, rate_per_service_tier_flex=0.8))])
        records = deepinfra.parse(body, self.aliases).records
        self.assertEqual([r["service_tier"] for r in records], ["standard", "priority", "flex"])
        self.assertAlmostEqual(records[2]["input_per_million"], 0.08)

    def test_deepinfra_refuses_unsupported_price_tables(self):
        body = json.dumps([dict(model_name=MODEL, pricing=dict(type="tokens", table=["new format"]))])
        with self.assertRaises(ValueError):
            deepinfra.parse(body, self.aliases)

    def test_novita_uses_dollar_decimal_not_integer_billing_units(self):
        body = json.dumps({"data": [dict(id=MODEL, context_size=131072, input_token_price_per_m=500, pricing=dict(prompt=dict(price_per_m=500, price_per_m_decimal="0.05"), completion=dict(price_per_m=2500, price_per_m_decimal="0.25")))]})
        parsed = novita.parse(body, self.aliases)
        self.assertEqual(parsed.records[0]["input_per_million"], 0.05)
        self.assertEqual(parsed.records[0]["output_per_million"], 0.25)

    def test_novita_refuses_ambiguous_units(self):
        body = json.dumps({"data": [dict(id=MODEL, pricing=dict(prompt=dict(price_per_m=500), completion=dict(price_per_m=2500)))]})
        with self.assertRaises(KeyError):
            novita.parse(body, self.aliases)

    def test_together_official_markdown(self):
        parsed = together.parse((FIXTURES / "together.md").read_text(), self.aliases)
        self.assertEqual(len(parsed.records), 2)
        self.assertEqual(parsed.records[0]["quantization"], "MXFP4")
        self.assertIsNone(parsed.records[0]["cache_read_per_million"])
        self.assertEqual(parsed.records[1]["variant"], "turbo")

    def test_fireworks_standard_priority_and_cache(self):
        parsed = fireworks.parse((FIXTURES / "fireworks.md").read_text(), self.aliases)
        self.assertEqual([r["service_tier"] for r in parsed.records], ["standard", "priority"])
        self.assertEqual(parsed.records[0]["cache_read_per_million"], 0.015)
        self.assertIsNone(parsed.records[0]["context_window"])
        self.assertFalse(parsed.authoritative_catalog)

    def test_groq_html_and_contact_sales_exclusion(self):
        parsed = groq.parse((FIXTURES / "groq.html").read_text(), self.aliases)
        self.assertEqual(len(parsed.records), 1)
        self.assertEqual(parsed.records[0]["context_window"], 131072)
        self.assertEqual(parsed.records[0]["output_per_million"], 0.6)

    def test_empty_or_changed_sources_are_failures_not_removals(self):
        for parser, body in [(deepinfra, "[]"), (novita, '{"data": []}'), (together, "Login required"), (fireworks, "New page layout"), (groq, "<html>Blocked</html>")]:
            with self.subTest(provider=parser.__name__):
                with self.assertRaises(ValueError):
                    parser.parse(body, self.aliases)

    def test_invalid_prices_and_currency_are_rejected(self):
        for value in (-1, "nan", "Infinity", None, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    number(value)
        with self.assertRaises(ValueError):
            normalize(dict(record(), currency="EUR"), self.aliases, TIME, HASH)

    def test_normalization_has_stable_ids_and_keeps_tiers(self):
        standard, _ = normalize(record(), self.aliases, TIME, HASH)
        priority, _ = normalize(record(service_tier="priority"), self.aliases, TIME, HASH)
        later, _ = normalize(record(input_price=0.08), self.aliases, "2026-10-04T12:00:00Z", HASH)
        self.assertEqual(standard["id"], later["id"])
        self.assertNotEqual(standard["id"], priority["id"])


class HistoryTests(unittest.TestCase):
    def setUp(self):
        _, self.aliases = catalog()
        self.offerings, self.latest, self.history, self.changes = {}, {}, [], []

    def apply(self, records=None, time=TIME, authoritative=True):
        return apply_snapshot("novita", collection(records, authoritative), self.aliases, time, self.offerings, self.latest, self.history, self.changes)

    def test_change_only_observations_are_append_only(self):
        self.apply()
        first = copy.deepcopy(self.history[0])
        self.apply(time="2026-10-03T13:00:00Z")
        self.assertEqual(len(self.history), 1)
        self.apply(time="2026-10-04T12:00:00Z")
        self.assertEqual(len(self.history), 1)
        self.apply([record(output_price=0.2)], time="2026-10-04T13:00:00Z")
        self.assertEqual(len(self.history), 2)
        self.assertEqual(self.history[0], first)
        cut = [c for c in self.changes if c["kind"] == "price_changed"][0]
        self.assertEqual(cut["change_pct"], -20)

    def test_first_seen_is_not_a_historical_price_change(self):
        self.apply()
        self.assertEqual(self.changes[0]["kind"], "offering_added")
        self.assertFalse(any(c["kind"] == "price_changed" for c in self.changes))

    def test_bad_partial_snapshot_does_not_mutate_good_state(self):
        self.apply()
        before = copy.deepcopy((self.offerings, self.latest, self.history, self.changes))
        with self.assertRaises(ValueError):
            self.apply([record(input_price=0.01), record("openai/gpt-oss-20b", input_price=-1)])
        self.assertEqual(before, (self.offerings, self.latest, self.history, self.changes))

    def test_duplicates_are_rejected_before_mutation(self):
        with self.assertRaises(ValueError):
            self.apply([record(), record()])
        self.assertEqual(self.offerings, {})

    def test_removals_require_successful_full_catalog(self):
        self.apply([record(), record("openai/gpt-oss-20b")])
        self.apply([record()], time="2026-10-04T12:00:00Z", authoritative=False)
        self.assertEqual(sum(o["active"] for o in self.offerings.values()), 2)
        self.apply([record()], time="2026-10-05T12:00:00Z", authoritative=True)
        self.assertEqual(sum(o["active"] for o in self.offerings.values()), 1)
        self.assertEqual(self.changes[-1]["kind"], "offering_removed")
        self.apply([record(), record("openai/gpt-oss-20b")], time="2026-10-06T12:00:00Z")
        self.assertEqual(self.changes[-1]["kind"], "offering_restored")

    def test_metadata_changes_and_unknown_cache_transitions(self):
        self.apply()
        self.apply([record(cache_read_per_million=0.01, quantization="FP8")], time="2026-10-04T12:00:00Z")
        self.assertTrue(any(c["kind"] == "offering_updated" for c in self.changes))
        cache = next(c for c in self.changes if c["field"] == "cache_read_per_million")
        self.assertIsNone(cache["old"])
        self.assertIsNone(cache["change_pct"])

    def test_zero_price_has_no_division_by_zero(self):
        self.apply()
        offering = next(iter(self.offerings.values()))
        self.assertIsNone(event("price_changed", offering, TIME, "input_per_million", 0, 0.1)["change_pct"])

    def test_empty_snapshot_cannot_remove_every_offering(self):
        self.apply()
        with self.assertRaises(ValueError):
            self.apply([])
        self.assertTrue(next(iter(self.offerings.values()))["active"])

    def test_failed_run_preserves_files_and_records_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch("scripts.collect.novita.collect", return_value=collection()), patch("scripts.collect.utc_now", return_value=TIME):
                self.assertEqual(run(path, ["novita"]), 0)
            before = {name: (path / name).read_bytes() for name in ("offerings.json", "latest_prices.json", "price_history.csv", "changes.json", "provider_inventory.json")}
            with patch("scripts.collect.novita.collect", side_effect=RuntimeError("Source unavailable")), patch("scripts.collect.utc_now", return_value="2026-10-04T12:00:00Z"):
                self.assertEqual(run(path, ["novita"]), 1)
            self.assertEqual(before, {name: (path / name).read_bytes() for name in before})
            status = json.loads((path / "status.json").read_text())
            self.assertEqual(status["providers"][0]["state"], "error")
            self.assertEqual(status["providers"][0]["last_success_at"], TIME)

    def test_csv_prefix_preserved_and_null_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch("scripts.collect.novita.collect", return_value=collection()), patch("scripts.collect.utc_now", return_value=TIME):
                run(path, ["novita"])
            before = (path / "price_history.csv").read_bytes()
            with patch("scripts.collect.novita.collect", return_value=collection()), patch("scripts.collect.utc_now", return_value="2026-10-04T12:00:00Z"):
                run(path, ["novita"])
            self.assertTrue((path / "price_history.csv").read_bytes().startswith(before))
            self.assertIsNone(read_history(path / "price_history.csv")[0]["cache_read_per_million"])

    def test_provider_inventory_keeps_content_addressed_source_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            first_body = '{"models":[{"id":"model-a","input_per_million":1}]}'
            with patch("scripts.collect.novita.collect", return_value=collection(source_body=first_body)), patch("scripts.collect.utc_now", return_value=TIME):
                self.assertEqual(run(path, ["novita"]), 0)
            index = json.loads((path / "provider_inventory.json").read_text())
            provider = index["providers"][0]
            self.assertEqual(provider["version_count"], 1)
            first_path = path / provider["latest_path"]
            artifact = json.loads(first_path.read_text())
            self.assertEqual(artifact["payload_format"], "json")
            self.assertEqual(artifact["payload"]["models"][0]["id"], "model-a")
            second_body = '{"models":[{"id":"model-a","input_per_million":2}]}'
            with patch("scripts.collect.novita.collect", return_value=collection(source_body=second_body)), patch("scripts.collect.utc_now", return_value="2026-10-04T12:00:00Z"):
                self.assertEqual(run(path, ["novita"]), 0)
            index = json.loads((path / "provider_inventory.json").read_text())
            provider = index["providers"][0]
            self.assertEqual(provider["version_count"], 2)
            self.assertTrue(first_path.exists())
            latest = json.loads((path / provider["latest_path"]).read_text())
            self.assertEqual(latest["payload"]["models"][0]["input_per_million"], 2)

    def test_parse_failure_archives_source_but_retains_curated_prices(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch("scripts.collect.novita.collect", return_value=collection()), patch("scripts.collect.utc_now", return_value=TIME):
                self.assertEqual(run(path, ["novita"]), 0)
            old_price = json.loads((path / "latest_prices.json").read_text())[0]
            changed_body = '{"models":[{"new_provider_model":"new-unrecognized-model","price":7}]}'
            failed = collection(records=[], source_body=changed_body, parse_error="unknown model layout")
            with patch("scripts.collect.novita.collect", return_value=failed), patch("scripts.collect.utc_now", return_value="2026-10-04T12:00:00Z"):
                self.assertEqual(run(path, ["novita"]), 1)
            self.assertEqual(json.loads((path / "latest_prices.json").read_text())[0], old_price)
            index = json.loads((path / "provider_inventory.json").read_text())
            provider = index["providers"][0]
            self.assertEqual(provider["curated_parser_state"], "error")
            self.assertEqual(provider["curated_parser_error"], "unknown model layout")
            self.assertTrue((path / provider["latest_path"]).exists())

    def test_dry_run_does_not_write_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch("scripts.collect.novita.collect", return_value=collection()):
                self.assertEqual(run(path, ["novita"], dry_run=True), 0)
            self.assertEqual(list(path.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
