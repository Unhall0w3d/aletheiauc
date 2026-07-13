"""CUCM collector and rule factories, imported only for CUCM targets."""

from __future__ import annotations

from cisco_collab_health.collectors.base import Collector
from cisco_collab_health.interfaces import PreflightResult
from cisco_collab_health.rules.base import HealthRule


class CucmPlugin:
    key = "cucm"

    def collectors(
        self,
        preflight: PreflightResult | None,
        *,
        smoke_test: bool,
        diagnostic_capture: bool,
    ) -> list[Collector]:
        if smoke_test:
            from cisco_collab_health.collectors.sample import SampleCollector

            return [SampleCollector()]
        if preflight is None:
            return []
        collectors: list[Collector] = []
        if "axl" in preflight.transport_available_interfaces:
            from cisco_collab_health.collectors.axl import AxlCollector

            collectors.append(AxlCollector())
        if diagnostic_capture:
            from cisco_collab_health.collectors.diagnostic import DiagnosticCaptureCollector

            collectors.append(DiagnosticCaptureCollector(preflight.transport_available_interfaces))
        return collectors

    def rules(self) -> list[HealthRule]:
        from cisco_collab_health.rules.basic import (
            CertificateValidityRule,
            ConfigurationInventorySummaryRule,
            DeviceInventorySummaryRule,
            DeviceLoadRule,
            DeviceLoadSummaryRule,
            FirmwareDownloadRule,
            RegistrationSummaryRule,
            ServiceRuntimeRule,
            ServiceSummaryRule,
            SipTrunkRuntimeRule,
        )

        return [
            CertificateValidityRule(),
            DeviceLoadRule(),
            DeviceInventorySummaryRule(),
            RegistrationSummaryRule(),
            SipTrunkRuntimeRule(),
            ServiceSummaryRule(),
            ServiceRuntimeRule(),
            DeviceLoadSummaryRule(),
            FirmwareDownloadRule(),
            ConfigurationInventorySummaryRule(),
        ]


def plugin() -> CucmPlugin:
    return CucmPlugin()
