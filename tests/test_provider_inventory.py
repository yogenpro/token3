import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.provider_inventory import prepare_source


class ProviderInventoryTests(unittest.TestCase):
    def result(self, body, url="https://provider.example/pricing", source_urls=None):
        return SimpleNamespace(
            source_payload=body,
            source_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
            source_url=url,
            source_urls=source_urls,
        )

    def test_json_source_payload_is_structured_and_content_addressed(self):
        with tempfile.TemporaryDirectory() as directory:
            body = '{"models":[{"id":"model-a","prices":{"image":"$0.04/image"}}]}'
            urls = ["https://provider.example/page-1", "https://provider.example/page-2"]
            row, artifact = prepare_source("vendor", "Vendor", self.result(body, source_urls=urls), "2026-10-03T12:00:00Z", Path(directory), {})
            self.assertEqual(row["source_urls"], urls)
            self.assertEqual(artifact["source_urls"], urls)
            self.assertEqual(hashlib.sha256(artifact["source_body"].encode()).hexdigest(), artifact["source_sha256"])
            self.assertEqual(row["payload_format"], "json")
            self.assertEqual(row["version_count"], 1)
            self.assertEqual(artifact["payload"]["models"][0]["prices"]["image"], "$0.04/image")
            self.assertTrue(row["latest_path"].endswith(row["source_sha256"] + ".json"))

    def test_same_source_updates_last_seen_without_creating_a_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            body = '{"models":[]}'
            row, artifact = prepare_source("vendor", "Vendor", self.result(body), "2026-10-03T12:00:00Z", path, {})
            (path / row["latest_path"]).parent.mkdir(parents=True)
            (path / row["latest_path"]).write_text(json.dumps(artifact))
            row2, artifact2 = prepare_source("vendor", "Vendor", self.result(body), "2026-10-04T12:00:00Z", path, {"vendor": row})
            self.assertIsNone(artifact2)
            self.assertEqual(row2["version_count"], 1)
            self.assertEqual(row2["first_seen_at"], "2026-10-03T12:00:00Z")
            self.assertEqual(row2["last_seen_at"], "2026-10-04T12:00:00Z")

    def test_changed_source_adds_a_version_and_keeps_the_old_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            first, _ = prepare_source("vendor", "Vendor", self.result('{"price":1}'), "2026-10-03T12:00:00Z", path, {})
            second, artifact = prepare_source("vendor", "Vendor", self.result('{"price":2}'), "2026-10-04T12:00:00Z", path, {"vendor": first})
            self.assertEqual(second["version_count"], 2)
            self.assertEqual(len({x["source_sha256"] for x in second["versions"]}), 2)
            self.assertEqual(artifact["payload"]["price"], 2)
            self.assertNotEqual(first["latest_path"], second["latest_path"])

    def test_payload_hash_and_official_https_url_are_required(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            prepare_source("vendor", "Vendor", SimpleNamespace(source_payload="x", source_sha256="0" * 64, source_url="https://provider.example"), "2026-10-03T12:00:00Z", Path("."), {})
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            prepare_source("vendor", "Vendor", self.result("<table><tr><td>$1/image</td></tr></table>", "http://provider.example/pricing"), "2026-10-03T12:00:00Z", Path("."), {})

    def test_markdown_and_html_pricing_documents_are_preserved_exactly(self):
        for body, expected in [("# Pricing\n\n| Model | Price |\n|---|---|\n| A | $1/image |", "markdown"), ("<html><table><tr><td>$1/image</td></tr></table></html>", "html")]:
            with self.subTest(expected=expected):
                row, artifact = prepare_source("vendor", "Vendor", self.result(body), "2026-10-03T12:00:00Z", Path("."), {})
                self.assertEqual(row["payload_format"], expected)
                self.assertEqual(artifact["payload"], body)


if __name__ == "__main__":
    unittest.main()
