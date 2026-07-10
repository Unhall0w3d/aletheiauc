"""Tests for captured diagnostic HTTP GET requests."""

from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch

from cisco_collab_health.artifacts import ArtifactStore
from cisco_collab_health.models.runtime import CollectionContext
from cisco_collab_health.transport.http import CapturedHttpClient


class FakeResponse:
    status = 200
    reason = "OK"
    headers = {"content-type": "text/xml", "set-cookie": "secret"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return b"<definitions />"


class CapturedHttpClientTests(unittest.TestCase):
    def test_get_captures_redacted_wsdl_and_attempt_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore.create(tmpdir, "lab")
            context = CollectionContext(
                gui_username="apiuser",
                gui_password="secret",
                artifact_store=store,
            )
            endpoint = "https://192.0.2.10:8443/service?wsdl"
            with patch(
                "cisco_collab_health.transport.http.urllib.request.urlopen",
                return_value=FakeResponse(),
            ):
                response = CapturedHttpClient().get(
                    endpoint,
                    context,
                    node="192.0.2.10",
                    interface="sample",
                    operation="wsdl",
                )

            request_path = (
                store.root / "nodes/192.0.2.10/api/sample/wsdl/request.txt"
            )
            response_path = (
                store.root / "nodes/192.0.2.10/api/sample/wsdl/response.txt"
            )
            attempts = [
                json.loads(line)
                for line in (store.root / "operation_attempts.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            request_text = request_path.read_text(encoding="utf-8")
            response_text = response_path.read_text(encoding="utf-8")

        self.assertEqual(response.body, "<definitions />")
        self.assertNotIn("Authorization", request_text)
        self.assertIn("set-cookie: <redacted>", response_text)
        self.assertEqual(attempts[0]["outcome"], "success")
        self.assertEqual(attempts[0]["http_status"], 200)
        self.assertGreater(attempts[0]["response_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
