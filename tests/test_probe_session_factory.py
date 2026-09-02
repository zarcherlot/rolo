from pathlib import Path

from rolo.agent_tools import (
    NativeToolStatus,
    create_profile_native_tool_session,
)
from rolo.target_ref import LocalTargetRef
from rolo.targets.profiles import CredentialReference, TargetProfileStore


def test_profile_session_factory_builds_a_bounded_local_surface(tmp_path: Path) -> None:
    config_root = tmp_path / "config"
    artifact_root = tmp_path / "artifacts"
    TargetProfileStore(config_root).create(
        robot_id="localbot",
        target=LocalTargetRef(workspace=tmp_path),
        credential=CredentialReference(kind="ssh-agent", reference="ssh-agent:default"),
    )

    session = create_profile_native_tool_session(
        "localbot",
        config_root=config_root,
        artifact_root=artifact_root,
        ttl_s=60,
        max_calls=2,
        native_executor=lambda *args, **kwargs: type(
            "Completed", (), {"returncode": 0, "stdout": "Linux local\n", "stderr": ""}
        )(),
    )
    try:
        tools = session.list_tools()
        result = session.invoke("native.linux.host.inspect", {"mode": "status"})
    finally:
        session.close()

    assert tools
    assert result.status in {NativeToolStatus.SUCCEEDED, NativeToolStatus.UNAVAILABLE}
    assert result.evidence_refs
    assert list(artifact_root.rglob("*.json"))
