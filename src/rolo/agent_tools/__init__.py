"""Bounded tools that an Adapt Agent may execute without a Canonical Operation wrapper."""

from rolo.agent_tools.broker import NativeToolBroker, native_broker_request
from rolo.agent_tools.native_tools import (
    AgentNativeRunner,
    AgentNativeToolDescriptor,
    AgentNativeToolResult,
    NativeToolInvocation,
    NativeToolParameter,
    NativeToolStatus,
    default_agent_native_catalog,
    load_agent_native_catalog,
    native_operation_family_map,
    reduced_agent_native_catalog,
)
from rolo.agent_tools.rollout import (
    NativeToolParityReport,
    NativeToolRolloutDecision,
    NativeToolRunSummary,
    build_native_operation_parity_report,
    decide_native_tool_rollout,
    summarize_native_tool_run,
)
from rolo.agent_tools.session import (
    NativeToolSession,
    NativeToolSessionAuthorizationError,
    NativeToolSessionBudget,
    NativeToolSessionBudgetError,
    NativeToolSessionDescriptor,
    native_catalog_sha256,
)

__all__ = [
    "AgentNativeRunner",
    "AgentNativeToolDescriptor",
    "AgentNativeToolResult",
    "NativeToolStatus",
    "NativeToolInvocation",
    "NativeToolParameter",
    "default_agent_native_catalog",
    "load_agent_native_catalog",
    "native_operation_family_map",
    "reduced_agent_native_catalog",
    "NativeToolSession",
    "NativeToolSessionAuthorizationError",
    "NativeToolSessionBudget",
    "NativeToolSessionBudgetError",
    "NativeToolSessionDescriptor",
    "native_catalog_sha256",
    "NativeToolBroker",
    "native_broker_request",
    "NativeToolRolloutDecision",
    "NativeToolRunSummary",
    "NativeToolParityReport",
    "build_native_operation_parity_report",
    "decide_native_tool_rollout",
    "summarize_native_tool_run",
]
