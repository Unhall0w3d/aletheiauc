"""CER collector factory, loaded only for Emergency Responder assessment targets."""

from __future__ import annotations

from cisco_collab_health.collectors.base import Collector
from cisco_collab_health.interfaces import PreflightResult
from cisco_collab_health.rules.base import HealthRule


class CerPlugin:
    key = "cer"

    def collectors(self, preflight: PreflightResult | None, *, smoke_test: bool, diagnostic_capture: bool) -> list[Collector]:
        del preflight
        if smoke_test:
            from cisco_collab_health.collectors.sample import SampleCollector
            return [SampleCollector()]
        if not diagnostic_capture:
            return []
        from cisco_collab_health.collectors.cer import CerApiCollector
        from cisco_collab_health.collectors.ucos_platform import CER_COMMAND_CATALOG, UcosPlatformCollector
        return [
            CerApiCollector(),
            UcosPlatformCollector(technology="cer", product_label="Cisco Emergency Responder", catalog=CER_COMMAND_CATALOG),
        ]

    def rules(self) -> list[HealthRule]:
        return []


def plugin() -> CerPlugin:
    return CerPlugin()
