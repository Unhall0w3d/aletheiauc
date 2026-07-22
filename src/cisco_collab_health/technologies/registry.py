"""Lazy registry for technology-specific assessment components."""

from __future__ import annotations

from collections.abc import Iterable
from importlib import import_module
from typing import Protocol, cast

from cisco_collab_health.collectors.base import Collector
from cisco_collab_health.interfaces import PreflightResult
from cisco_collab_health.rules.base import HealthRule


class TechnologyPlugin(Protocol):
    """Technology-owned factories consumed by the shared assessment workflow."""

    key: str

    def collectors(
        self,
        preflight: PreflightResult | None,
        *,
        smoke_test: bool,
        diagnostic_capture: bool,
    ) -> list[Collector]: ...

    def rules(self) -> list[HealthRule]: ...


_PLUGIN_MODULES = {
    "cer": "cisco_collab_health.technologies.cer.plugin",
    "cuc": "cisco_collab_health.technologies.cuc.plugin",
    "cucm": "cisco_collab_health.technologies.cucm.plugin",
    "imp": "cisco_collab_health.technologies.imp.plugin",
}


def load_plugin(technology: str) -> TechnologyPlugin | None:
    """Load one implemented technology plugin only when it is in assessment scope."""

    module_path = _PLUGIN_MODULES.get(technology.strip().lower())
    if module_path is None:
        return None
    module = import_module(module_path)
    return cast(TechnologyPlugin, module.plugin())


def load_plugins(technologies: Iterable[str]) -> list[TechnologyPlugin]:
    """Load each supported in-scope plugin once, retaining requested order."""

    plugins: list[TechnologyPlugin] = []
    seen: set[str] = set()
    for technology in technologies:
        key = technology.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        plugin = load_plugin(key)
        if plugin is not None:
            plugins.append(plugin)
    return plugins
