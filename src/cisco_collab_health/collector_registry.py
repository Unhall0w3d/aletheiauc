"""Collector selection for assessment runs."""

from __future__ import annotations

from cisco_collab_health.collectors.base import Collector
from cisco_collab_health.interfaces import PreflightResult
from cisco_collab_health.technologies import load_plugin


def select_collectors(
    preflight: PreflightResult | None,
    *,
    smoke_test: bool = False,
    diagnostic_capture: bool = False,
    product: str = "cucm",
) -> list[Collector]:
    """Select collectors for the current runtime mode and preflight result."""

    plugin = load_plugin(product)
    if plugin is None:
        return []
    return plugin.collectors(
        preflight,
        smoke_test=smoke_test,
        diagnostic_capture=diagnostic_capture,
    )
