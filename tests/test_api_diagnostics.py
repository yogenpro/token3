import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from providers.common import Collection
from scripts.inspect_fireworks_catalog import main, report


PUBLIC = "accounts/fireworks/models/gpt-oss-120b"


class APIDiagnosticTests(unittest.TestCase):
    def test_only_reviewed_public_model_prices_are_sampled(self):
        payload = dict(data=[dict(id=PUBLIC, serverless_mode="default", pricing=[dict(sku="LLM input tokens (uncached)",amount="0.15",unit="1M tokens")]),
                             dict(id="private-owner/model",private=True,serverless_mode="private-custom-mode",pricing={"private-price-identifier": "12"}),
                             dict(id="unreviewed/model",pricing={"unreviewed-price-identifier":"4"})])
        result=report(payload,{PUBLIC:"openai/gpt-oss-120b"});encoded=json.dumps(result)
        self.assertEqual(result["model_rows"],3)
        self.assertEqual(len(result["reviewed_public_model_samples"]),1)
        self.assertNotIn("private-owner",encoded)
        self.assertNotIn("private-custom-mode",encoded)
        self.assertNotIn("private-price-identifier",encoded)
        self.assertNotIn("unreviewed-price-identifier",encoded)

    def test_missing_null_and_empty_price_lists_are_distinct(self):
        result=report(dict(data=[dict(id="a"),dict(id="b",pricing=None),dict(id="c",pricing=[])]),{})
        self.assertEqual(result["pricing_shapes"],dict(missing=1,NoneType=1,list=1))

    def test_credential_echo_is_rejected_before_any_diagnostic_output(self):
        key="fixture-secret";result=Collection([],"https://example.com", "a"*64,source_payload=key,source_kind="api")
        output=io.StringIO()
        with patch.dict(os.environ,{"FIREWORKS_API_KEY":" "+key+"\n"}),patch("scripts.inspect_fireworks_catalog.catalog",return_value=({},{})),patch("scripts.inspect_fireworks_catalog.fireworks.collect",return_value=result),redirect_stdout(output):
            with self.assertRaises(ValueError):main()
        self.assertEqual(output.getvalue(),"")

    def test_failed_authentication_fallback_is_reported_with_key_redacted(self):
        key="fixture-secret";result=Collection([],"https://example.com", "a"*64,source_payload="pricing",source_kind="documentation",fallback_reason="rejected "+key)
        output=io.StringIO()
        with patch.dict(os.environ,{"FIREWORKS_API_KEY":key}),patch("scripts.inspect_fireworks_catalog.catalog",return_value=({},{})),patch("scripts.inspect_fireworks_catalog.fireworks.collect",return_value=result),redirect_stdout(output):
            with self.assertRaises(ValueError):main()
        self.assertNotIn(key,output.getvalue())
        self.assertIn("[redacted]",output.getvalue())


if __name__ == "__main__":
    unittest.main()
