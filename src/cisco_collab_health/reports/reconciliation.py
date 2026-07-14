"""Inventory/runtime reconciliation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from cisco_collab_health.models.facts import DeviceInventoryFact, DeviceRegistrationFact


@dataclass(frozen=True)
class InventoryRuntimeReconciliation:
    """Name-based reconciliation between configured inventory and runtime registrations."""

    inventory_count: int
    runtime_count: int
    matched_names: list[str]
    inventory_only: list[DeviceInventoryFact]
    runtime_only: list[DeviceRegistrationFact]

    @property
    def known_non_runtime(self) -> list[DeviceInventoryFact]:
        return [device for device in self.inventory_only if _is_known_non_runtime(device)]

    @property
    def registration_capable_or_unclassified(self) -> list[DeviceInventoryFact]:
        return [device for device in self.inventory_only if not _is_known_non_runtime(device)]

    @property
    def runtime_only_resources(self) -> list[DeviceRegistrationFact]:
        """CUCM infrastructure returned by the supplemental all-class RIS query."""

        return [
            registration
            for registration in self.runtime_only
            if runtime_resource_category(registration) is not None
        ]

    @property
    def runtime_only_endpoints(self) -> list[DeviceRegistrationFact]:
        """Runtime records not matched to inventory and not recognized as infrastructure."""

        return [
            registration
            for registration in self.runtime_only
            if runtime_resource_category(registration) is None
        ]


def build_inventory_runtime_reconciliation(
    devices: list[DeviceInventoryFact],
    registrations: list[DeviceRegistrationFact],
) -> InventoryRuntimeReconciliation:
    """Build an initial name-based reconciliation between inventory and runtime facts."""

    registration_names = {_normalize_name(registration.name) for registration in registrations}
    device_names = {_normalize_name(device.name) for device in devices}
    matched_names = sorted(device_names & registration_names)

    return InventoryRuntimeReconciliation(
        inventory_count=len(devices),
        runtime_count=len(registrations),
        matched_names=matched_names,
        inventory_only=[
            device for device in devices if _normalize_name(device.name) not in registration_names
        ],
        runtime_only=[
            registration
            for registration in registrations
            if _normalize_name(registration.name) not in device_names
        ],
    )


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _is_known_non_runtime(device: DeviceInventoryFact) -> bool:
    """Conservatively recognize configuration templates that never register to RIS."""

    return (device.model or "").strip().lower() == "universal device template"


def runtime_resource_category(registration: DeviceRegistrationFact) -> str | None:
    """Classify non-endpoint CUCM runtime resources using RIS class and model metadata."""

    device_class = (registration.device_class or "").strip().casefold()
    model_code = (registration.runtime_model_code or registration.model or "").strip()
    model = (registration.model or "").strip().casefold()
    name = registration.name.strip().casefold()
    protocol = (registration.protocol or "").strip().casefold()
    combined = " ".join((model, name, protocol))

    if device_class == "siptrunk" or "sip trunk" in combined or "sip-trunk" in combined:
        return "SIP Trunks"
    if device_class == "huntlist" or model_code == "90" or "route list" in combined:
        return "Route Lists"
    if device_class == "h323":
        return "H.323 Gateways"
    if device_class == "gateway" or any(
        value in combined for value in ("gateway", "mgcp", "vg gateway")
    ):
        return "Gateways"
    if device_class == "cti" and model_code == "73":
        return "CTI Route Points"
    if device_class == "mediaresources":
        return {
            "50": "Conference Bridges",
            "70": "Music On Hold",
            "110": "Media Termination Points",
            "112": "Transcoders",
            "126": "Annunciators",
            "36219": "IVR Media Resources",
        }.get(model_code, "Other Media Resources")
    return None
