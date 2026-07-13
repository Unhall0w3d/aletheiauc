"""Tests for technology-scoped lazy component selection."""

from __future__ import annotations

import unittest

from cisco_collab_health.collector_registry import select_collectors
from cisco_collab_health.technologies import load_plugin, load_plugins


class TechnologyPluginTests(unittest.TestCase):
    def test_supported_plugins_are_loaded_only_for_requested_technologies(self) -> None:
        plugins = load_plugins(["cuc", "cuc", "cucm", "cer"])

        self.assertEqual([plugin.key for plugin in plugins], ["cuc", "cucm"])
        self.assertIsNone(load_plugin("cer"))

    def test_cuc_diagnostic_selection_uses_cuc_plugin_collectors(self) -> None:
        collectors = select_collectors(
            None,
            product="cuc",
            diagnostic_capture=True,
        )

        self.assertEqual(
            [collector.name for collector in collectors],
            ["cuc", "cuc_platform_cli"],
        )

    def test_cucm_without_preflight_does_not_load_collectors(self) -> None:
        self.assertEqual(select_collectors(None, product="cucm"), [])
