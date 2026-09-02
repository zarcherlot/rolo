"""Independent conformance checks for the v2 read-only Tool Surface."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.agent_tools.native_tools import AgentNativeToolDescriptor
from rolo.agent_tools.session import NativeToolSessionDescriptor, native_catalog_sha256


class ToolConformanceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=96)
    status: Literal["PASS", "FAIL"]
    detail: str = Field(min_length=1, max_length=512)


class ToolConformanceReport(BaseModel):
    """A reproducible, non-Agent verdict over a frozen Tool Surface."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-tool-conformance/v1"] = "rolo-tool-conformance/v1"
    target_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    surface_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["PASS", "FAIL"]
    checks: list[ToolConformanceCheck] = Field(min_length=1, max_length=512)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def conform_tool_surface(
    session: NativeToolSessionDescriptor,
    descriptors: list[AgentNativeToolDescriptor],
) -> ToolConformanceReport:
    """Verify that the session and every published descriptor are safe to consume."""

    checks: list[ToolConformanceCheck] = []
    actual_digest = native_catalog_sha256(descriptors)
    checks.append(
        ToolConformanceCheck(
            name="catalog_digest",
            status="PASS" if actual_digest == session.native_catalog_sha256 else "FAIL",
            detail="session digest matches the complete descriptor catalog"
            if actual_digest == session.native_catalog_sha256
            else "session digest does not match the complete descriptor catalog",
        )
    )
    ids = [item.tool_id for item in descriptors]
    checks.append(
        ToolConformanceCheck(
            name="unique_tool_ids",
            status="PASS" if len(ids) == len(set(ids)) else "FAIL",
            detail="all tool IDs are unique" if len(ids) == len(set(ids)) else "duplicate tool IDs",
        )
    )
    allowed = set(session.allowed_tools)
    unknown = sorted(allowed - set(ids))
    checks.append(
        ToolConformanceCheck(
            name="session_allowlist",
            status="PASS" if not unknown else "FAIL",
            detail="session allowlist is contained in the catalog"
            if not unknown
            else f"session allowlist contains unknown tools: {unknown}",
        )
    )
    for descriptor in descriptors:
        valid = (
            descriptor.access == "read"
            and descriptor.argv_template
            and descriptor.argv_template[0] == descriptor.executable
            and all("{" not in item and "}" not in item for item in descriptor.argv_template)
            and descriptor.max_duration_s <= 120
            and descriptor.max_output_bytes <= 1_000_000
        )
        checks.append(
            ToolConformanceCheck(
                name=f"descriptor:{descriptor.tool_id}",
                status="PASS" if valid else "FAIL",
                detail="fixed-argv read-only bounds are valid"
                if valid
                else "descriptor violates fixed-argv read-only bounds",
            )
        )
    status = "PASS" if all(item.status == "PASS" for item in checks) else "FAIL"
    return ToolConformanceReport(
        target_id=session.robot_id,
        session_id=session.session_id,
        surface_digest=session.native_catalog_sha256,
        status=status,
        checks=checks,
    )
