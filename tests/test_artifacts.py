"""Tests for local assessment artifact storage."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cisco_collab_health.artifacts import ArtifactStore


class ArtifactStoreTests(unittest.TestCase):
    def test_artifact_store_writes_manifest_and_node_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore.create(Path(tmpdir), "Lab Cluster")
            manifest = store.write_manifest({"publisher_ip": "192.0.2.10"})
            preflight = store.write_node_json(
                "192.0.2.10",
                "preflight",
                "publisher_preflight.json",
                {"status": "ok"},
            )
            command = store.write_command_output(
                "192.0.2.10",
                "utils dbreplication runtimestate",
                "Replication status output",
            )

            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))

        self.assertEqual(manifest_payload["profile_name"], "Lab Cluster")
        self.assertTrue(str(preflight).endswith("nodes/192.0.2.10/preflight/publisher_preflight.json"))
        self.assertIn("utils_dbreplication_runtimestate.txt", str(command))

    def test_api_exchange_is_stored_by_node_interface_and_operation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore.create(Path(tmpdir), "lab")
            request, response = store.write_api_exchange(
                "192.0.2.10",
                "axl",
                "getCCMVersion",
                request="<request />",
                response="<response />",
            )

        self.assertTrue(str(request).endswith("nodes/192.0.2.10/api/axl/getCCMVersion/request.txt"))
        self.assertTrue(str(response).endswith("nodes/192.0.2.10/api/axl/getCCMVersion/response.txt"))


if __name__ == "__main__":
    unittest.main()
