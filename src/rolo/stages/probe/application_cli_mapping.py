"""Bounded application CLI route extraction for the Probe evidence bundle.

The MVP records only target-observed self-description. Semantic candidate design is
owned by the Agent; this module deliberately does not infer or maintain an operation
registry.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from rolo.core.models import ProbeResult, RouteEvidence
from rolo.stages.probe.active_discovery import HelpProbeStatus
from rolo.stages.probe.routes import probe_routes


def canonical_executable_name(value: str) -> str:
    """Normalize a target path without applying controller-specific path semantics."""
    name = str(value).replace("\\", "/").rsplit("/", 1)[-1]
    for suffix in (".exe", ".cmd", ".bat", ".ps1", ".py"):
        if name.casefold().endswith(suffix):
            return name[: -len(suffix)]
    return name


class ApplicationCliRouteProvider:
    """Convert verified bounded help records into observed CLI routes."""

    interface_type = "application/cli"

    def declared_routes(self, projects: Sequence[Mapping[str, Any]]) -> list[RouteEvidence]:
        routes: dict[str, RouteEvidence] = {}
        for project in projects:
            root = str(project.get("root", "unknown"))
            for entrypoint in project.get("entrypoints", []):
                if not isinstance(entrypoint, Mapping):
                    continue
                raw_name = str(entrypoint.get("name", "")).strip()
                if not raw_name:
                    continue
                name = canonical_executable_name(raw_name)
                routes.setdefault(
                    f"cli:{name}",
                    RouteEvidence(
                        resource_id=f"cli:{name}",
                        kind="cli",
                        endpoint=name,
                        interface_type=self.interface_type,
                        evidence_origin="DECLARED_STATIC",
                        source=f"source:{root}#entrypoint/{name}",
                        limitations=[
                            "Source declaration does not prove target installation or availability"
                        ],
                    ),
                )
        return sorted(routes.values(), key=lambda item: item.resource_id)

    def observed_routes(
        self,
        records: Sequence[Any],
        *,
        bundle_payload_sha256: str,
        observed_at: datetime,
    ) -> list[RouteEvidence]:
        routes: dict[str, RouteEvidence] = {}
        for record in records:
            status = getattr(getattr(record, "help_probe", None), "status", None)
            if getattr(status, "value", status) != HelpProbeStatus.SUCCEEDED.value:
                continue
            if not (record.usage or record.parameters or record.subcommands):
                continue
            interface = {
                "usage": sorted(set(record.usage)),
                "parameters": sorted(set(record.parameters)),
                "subcommands": sorted(set(record.subcommands)),
            }
            digest = hashlib.sha256(
                json.dumps(interface, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                .encode("utf-8")
            ).hexdigest()
            canonical_name = canonical_executable_name(record.path)
            source = (
                f"target-evidence:{bundle_payload_sha256}#executable-help/{record.executable_id}"
            )
            for endpoint in sorted({canonical_name, record.path}):
                routes[f"cli:{endpoint}"] = RouteEvidence(
                    resource_id=f"cli:{endpoint}",
                    kind="cli",
                    endpoint=endpoint,
                    interface_type=self.interface_type,
                    interface_schema_sha256=digest,
                    provider_id=record.executable_id,
                    runtime_revision=record.executable_sha256,
                    observed_at=observed_at,
                    evidence_origin="OBSERVED_RUNTIME",
                    source=source,
                    limitations=[
                        "Bounded --help proves route identity and self-description only"
                    ],
                )
        return sorted(routes.values(), key=lambda item: item.resource_id)


def bind_declared_and_observed_routes(
    application_probe: ProbeResult,
    records: Sequence[Any],
    *,
    bundle_payload_sha256: str,
    observed_at: datetime,
) -> ProbeResult:
    """Merge target-observed CLI routes into an application Probe result."""
    existing = {route.resource_id: route for route in probe_routes(application_probe)}
    existing.update(
        {
            route.resource_id: route
            for route in ApplicationCliRouteProvider().observed_routes(
                records,
                bundle_payload_sha256=bundle_payload_sha256,
                observed_at=observed_at,
            )
        }
    )
    data = dict(application_probe.data)
    data["route_evidence"] = [
        route.model_dump(mode="json")
        for route in sorted(existing.values(), key=lambda item: item.resource_id)
    ]
    return application_probe.model_copy(update={"data": data})
