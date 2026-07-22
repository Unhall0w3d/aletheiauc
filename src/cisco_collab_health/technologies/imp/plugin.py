"""IM&P collector factory, loaded only for IM&P assessment targets."""

from __future__ import annotations

from cisco_collab_health.collectors.base import Collector
from cisco_collab_health.interfaces import PreflightResult
from cisco_collab_health.rules.base import HealthRule


class ImpPlugin:
    key = "imp"

    def collectors(self, preflight: PreflightResult | None, *, smoke_test: bool, diagnostic_capture: bool) -> list[Collector]:
        del preflight
        if smoke_test:
            from cisco_collab_health.collectors.sample import SampleCollector
            return [SampleCollector()]
        if not diagnostic_capture:
            return []
        from cisco_collab_health.collectors.ucos_platform import IM_PRESENCE_COMMAND_CATALOG, UcosPlatformCollector
        return [UcosPlatformCollector(technology="imp", product_label="Cisco IM and Presence", catalog=IM_PRESENCE_COMMAND_CATALOG)]

    def rules(self) -> list[HealthRule]:
        return []


def plugin() -> ImpPlugin:
    return ImpPlugin()
