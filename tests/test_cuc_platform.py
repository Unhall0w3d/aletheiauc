"""Tests for bounded Unity Connection UCOS CLI collection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cisco_collab_health.artifacts import ArtifactStore
from cisco_collab_health.collectors.cuc_platform import (
    CUC_SAFE_CLI_COMMANDS,
    CucPlatformCollector,
)
from cisco_collab_health.models.runtime import CollectionContext


class CucPlatformCollectorTests(unittest.TestCase):
    def test_collector_records_only_safe_commands_and_artifacts(self) -> None:
        commands: list[str] = []

        def executor(context: CollectionContext, command: str) -> str:
            del context
            commands.append(command)
            return f"output for {command}"

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = ArtifactStore.create(Path(tmpdir), "cuc", None)
            result = CucPlatformCollector(executor=executor).collect(
                CollectionContext(publisher_ip="192.0.2.20", artifact_store=artifacts)
            )

            self.assertEqual(commands, list(CUC_SAFE_CLI_COMMANDS))
            self.assertEqual(len(result.facts.platform_checks), len(CUC_SAFE_CLI_COMMANDS))
            self.assertEqual(len(list(artifacts.root.rglob("*.txt"))), len(CUC_SAFE_CLI_COMMANDS))
