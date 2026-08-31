from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from rolo.target_readiness import (
    TargetReadinessSummary,
    build_target_readiness_collection,
    build_target_readiness_summary,
    get_target_readiness_summary,
)
from rolo.target_ref import LocalTargetRef, parse_target_ref
from rolo.targets.profiles import CredentialReference, HostKeyDecision, TargetProfileStore


def _credential() -> CredentialReference:
    return CredentialReference(kind="ssh-agent", reference="ssh-agent:default")


def test_local_readiness_is_ready_without_exposing_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = TargetProfileStore(tmp_path / "config")
    profile = store.create(
        robot_id="demo_local",
        target=LocalTargetRef(workspace=workspace),
        credential=_credential(),
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    summary = build_target_readiness_summary(profile)
    payload = summary.model_dump(mode="json")
    assert summary.state == "READY"
    assert summary.reachable is True
    assert summary.workspace_accessible is True
    assert summary.host_key_pinned is None
    assert summary.companion == "NOT_REQUIRED"
    assert str(workspace) not in str(payload)
    assert summary.contains_secret_payloads is False


def test_missing_local_workspace_is_blocked(tmp_path: Path) -> None:
    store = TargetProfileStore(tmp_path / "config")
    profile = store.create(
        robot_id="demo_local",
        target=LocalTargetRef(workspace=tmp_path / "missing"),
        credential=_credential(),
    )

    summary = build_target_readiness_summary(profile)
    assert summary.state == "WORKSPACE_MISSING"
    assert summary.reachable is False
    assert summary.blockers == ["WORKSPACE_MISSING"]


def test_ssh_readiness_requires_pinned_host_key(tmp_path: Path) -> None:
    store = TargetProfileStore(tmp_path / "config")
    profile = store.create(
        robot_id="demo_ssh",
        target=parse_target_ref("ssh://alice@example.test/opt/rolo"),
        credential=_credential(),
    )

    summary = build_target_readiness_summary(profile)
    payload = summary.model_dump_json()
    assert summary.state == "HOST_KEY_REQUIRED"
    assert summary.host_key_pinned is False
    assert summary.freshness == "unknown"
    assert "example.test" not in payload
    assert "alice" not in payload
    assert "/opt/rolo" not in payload

    approved = profile.model_copy(
        update={
            "host_key": HostKeyDecision(
                status="APPROVED",
                host="example.test",
                fingerprint="SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            )
        }
    )
    summary = build_target_readiness_summary(approved)
    assert summary.state == "UNREACHABLE"
    assert summary.host_key_pinned is True


def test_collection_paginates_and_detail_uses_opaque_id(tmp_path: Path) -> None:
    config = tmp_path / "config"
    store = TargetProfileStore(config)
    for robot_id in ("demo_one", "demo_two", "demo_three"):
        store.create(
            robot_id=robot_id,
            target=LocalTargetRef(workspace=tmp_path),
            credential=_credential(),
        )

    page = build_target_readiness_collection(config, limit=2)
    assert page.total == 3
    assert [item.target_id for item in page.items] == ["demo_one", "demo_three"]
    assert page.next_offset == 2
    assert get_target_readiness_summary(config, "demo_two").target_id == "demo_two"
    assert get_target_readiness_summary(config, "does_not_exist") is None


def test_summary_rejects_secret_payloads_and_unsafe_text() -> None:
    with pytest.raises(ValidationError):
        TargetReadinessSummary(
            target_id="demo_one",
            target_kind="local",
            state="READY",
            reachable=True,
            host_key_pinned=None,
            workspace_accessible=True,
            companion="NOT_REQUIRED",
            blockers=["ssh://example.test"],
            diagnostics=[],
            limitations=[],
            observed_at=datetime.now(timezone.utc),
            freshness="fresh",
            producer_revision="0" * 64,
            contains_secret_payloads=True,
        )
