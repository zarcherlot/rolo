"""Opt-in smoke test for a real, dedicated Session Agent provider credential."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from rolo.targets.agent_broker import (
    SessionAgentSessionRecord,
    build_session_agent_tool_catalog,
)
from rolo.targets.agent_runtime import (
    CodexSessionAgentProvider,
    SessionAgentDecisionKind,
)


@pytest.mark.skipif(
    os.getenv("ROLO_RUN_REAL_SESSION_AGENT") != "1",
    reason="set ROLO_RUN_REAL_SESSION_AGENT=1 for the opt-in provider smoke test",
)
def test_real_session_agent_provider_returns_only_the_bounded_schema() -> None:
    api_key = os.environ.get("ROLO_SESSION_AGENT_API_KEY")
    if not api_key:
        pytest.fail("ROLO_SESSION_AGENT_API_KEY must be a dedicated provider credential")
    catalog = build_session_agent_tool_catalog()
    created_at = datetime.now(timezone.utc)
    session = SessionAgentSessionRecord(
        session_id="agent-session-" + "a" * 32,
        open_request_sha256="b" * 64,
        open_idempotency_sha256="c" * 64,
        principal="real-provider-smoke",
        permissions=[],
        allowed_target_ids=["alpha"],
        catalog_sha256=catalog.canonical_sha256(),
        max_tool_calls=2,
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=2),
    )
    provider = CodexSessionAgentProvider(
        api_key=api_key,
        model=os.environ.get("ROLO_SESSION_AGENT_MODEL"),
        base_url=os.environ.get(
            "ROLO_SESSION_AGENT_BASE_URL",
            "https://api.openai.com/v1",
        ),
        executable=os.environ.get("ROLO_SESSION_AGENT_EXECUTABLE", "codex"),
        timeout_s=120,
    )

    decision = provider.decide(
        message="只列出允许范围内的目标；不要执行写操作。",
        catalog=catalog,
        session=session,
    )

    assert decision.kind in set(SessionAgentDecisionKind)
    if decision.command is not None:
        assert decision.command.action in {tool.action for tool in catalog.tools}
        assert decision.command.target_id in {None, "alpha"}
