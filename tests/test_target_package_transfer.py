from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from base64 import b64encode
from pathlib import Path

import pytest
from pydantic import ValidationError

from rolo.targets import (
    TARGET_PACKAGE_SBOM_NAME,
    LocalTargetExecutor,
    TargetArchitecture,
    TargetExecutionErrorCode,
    TargetExecutionStatus,
    TargetPackageChunkStore,
    TargetPackageFile,
    TargetPackageFileRole,
    TargetPackageManifest,
    TargetPackageSignature,
    TargetPackageTransferOperation,
    TargetPackageTransferRequest,
    TargetPackageUploader,
    bind_target_package_sbom,
)
from rolo.targets.package_transfer import _PREINSTALL_TRANSFER_SCRIPT


class AcceptingVerifier:
    def verify(
        self,
        manifest: TargetPackageManifest,
        signature: TargetPackageSignature,
    ) -> None:
        signature.validate_manifest(manifest)
        if signature.key_id != "release-key-2026":
            raise ValueError("target package signature key is not pinned")


def _package(tmp_path: Path) -> tuple[Path, TargetPackageManifest]:
    root = tmp_path / "package"
    entrypoint = root / "bin/robotctl"
    runtime = root / "share/rolo/runtime.bin"
    entrypoint.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    entrypoint.write_bytes(b"#!/bin/sh\necho rolo\n" + b"e" * 700)
    runtime.write_bytes(bytes(range(256)) * 12)

    def item(path: Path, role: TargetPackageFileRole, mode: int) -> TargetPackageFile:
        payload = path.read_bytes()
        return TargetPackageFile(
            path=path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            mode=mode,
            role=role,
        )

    manifest = TargetPackageManifest(
        package_id="rolo-target",
        package_version="0.2.0",
        rolo_version="0.2.0",
        architecture=TargetArchitecture.X86_64,
        python_requires=">=3.10,<3.14",
        entrypoint="bin/robotctl",
        files=sorted(
            [
                item(entrypoint, TargetPackageFileRole.ENTRYPOINT, 0o755),
                item(runtime, TargetPackageFileRole.RUNTIME, 0o644),
            ],
            key=lambda value: value.path,
        ),
    )
    manifest, _, sbom_payload = bind_target_package_sbom(manifest)
    (root / TARGET_PACKAGE_SBOM_NAME).write_bytes(sbom_payload)
    signature = TargetPackageSignature(
        key_id="release-key-2026",
        manifest_sha256=manifest.canonical_sha256(),
        signature_base64=b64encode(b"s" * 64).decode("ascii"),
    )
    (root / "target-package.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "target-package.sig.json").write_text(
        signature.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return root, manifest


def _request(
    *,
    operation: TargetPackageTransferOperation,
    payload: bytes,
    offset: int = 0,
    file_payload: bytes | None = None,
) -> TargetPackageTransferRequest:
    complete = payload if file_payload is None else file_payload
    values: dict[str, object] = {
        "request_id": f"transfer-{operation.value.casefold()}-{offset}",
        "operation": operation,
        "package_id": "rolo-target",
        "manifest_sha256": "a" * 64,
        "path": "bin/robotctl",
        "file_sha256": hashlib.sha256(complete).hexdigest(),
        "file_size_bytes": len(complete),
    }
    if operation == TargetPackageTransferOperation.WRITE:
        values.update(
            {
                "offset_bytes": offset,
                "chunk_size_bytes": len(payload),
                "chunk_sha256": hashlib.sha256(payload).hexdigest(),
                "chunk_base64": b64encode(payload).decode("ascii"),
            }
        )
    return TargetPackageTransferRequest.model_validate(values)


def test_transfer_request_rejects_traversal_and_unbound_chunks() -> None:
    with pytest.raises(ValidationError, match="normalized and relative"):
        TargetPackageTransferRequest.model_validate(
            {
                **_request(
                    operation=TargetPackageTransferOperation.QUERY,
                    payload=b"abc",
                ).model_dump(),
                "path": "../escape",
            }
        )
    with pytest.raises(ValidationError, match="chunk digest mismatch"):
        TargetPackageTransferRequest.model_validate(
            {
                **_request(
                    operation=TargetPackageTransferOperation.WRITE,
                    payload=b"abc",
                ).model_dump(),
                "chunk_sha256": "0" * 64,
            }
        )


def test_chunk_store_reports_offset_and_completes_atomically(tmp_path: Path) -> None:
    store = TargetPackageChunkStore(tmp_path / "incoming")
    payload = b"abcdefgh"
    first = _request(
        operation=TargetPackageTransferOperation.WRITE,
        payload=payload[:3],
        file_payload=payload,
    )
    first_result = store.apply(first)
    query = _request(
        operation=TargetPackageTransferOperation.QUERY,
        payload=b"",
        file_payload=payload,
    )
    query_result = store.apply(query)
    stale_result = store.apply(first)
    second = _request(
        operation=TargetPackageTransferOperation.WRITE,
        payload=payload[3:],
        offset=3,
        file_payload=payload,
    )
    complete = store.apply(second)
    repeated = store.apply(query)

    assert first_result.received_size_bytes == 3
    assert query_result.received_size_bytes == 3
    assert stale_result.status == TargetExecutionStatus.FAILED
    assert stale_result.error_code == TargetExecutionErrorCode.OFFSET_MISMATCH
    assert complete.complete is True
    assert repeated.complete is True
    final = (
        store.root
        / "packages"
        / "rolo-target"
        / ("a" * 64)
        / "bin/robotctl"
    )
    assert final.read_bytes() == payload
    assert not list((store.root / "state").rglob("*.part"))


def test_chunk_store_discards_full_file_with_wrong_declared_digest(tmp_path: Path) -> None:
    store = TargetPackageChunkStore(tmp_path / "incoming")
    request = _request(
        operation=TargetPackageTransferOperation.WRITE,
        payload=b"actual",
    ).model_copy(update={"file_sha256": hashlib.sha256(b"different").hexdigest()})

    result = store.apply(request)

    assert result.status == TargetExecutionStatus.FAILED
    assert result.error_code == TargetExecutionErrorCode.INTEGRITY_ERROR
    assert result.received_size_bytes == 0
    assert not list((store.root / "state").rglob("*.part"))


def test_chunk_store_resumes_legacy_full_digest_state_file(tmp_path: Path) -> None:
    store = TargetPackageChunkStore(tmp_path / "incoming")
    payload = b"legacy-state"
    request = _request(
        operation=TargetPackageTransferOperation.QUERY,
        payload=b"",
        file_payload=payload,
    )
    state_root = store.root / "state" / request.package_id / request.manifest_sha256
    state_root.mkdir(parents=True)
    state_digest = hashlib.sha256(request.path.encode("utf-8")).hexdigest()
    legacy_state = state_root / f"{state_digest}.part"
    legacy_state.write_bytes(payload[:6])

    observed = store.apply(request)
    completed = store.apply(
        _request(
            operation=TargetPackageTransferOperation.WRITE,
            payload=payload[6:],
            offset=6,
            file_payload=payload,
        )
    )

    assert observed.received_size_bytes == 6
    assert completed.complete is True
    assert not legacy_state.exists()
    assert not (state_root / f"{state_digest[:32]}.part").exists()


def test_uploader_resumes_after_interruption_and_repeat_is_noop(tmp_path: Path) -> None:
    package, manifest = _package(tmp_path)
    incoming = tmp_path / "incoming"
    delegate = LocalTargetExecutor(transfer_root=incoming)

    class InterruptOnce:
        def __init__(self) -> None:
            self.calls = 0

        def transfer_package_chunk(self, request, *, cancel_event=None):  # type: ignore[no-untyped-def]
            self.calls += 1
            if self.calls == 8:
                raise ConnectionError("simulated connection loss")
            return delegate.transfer_package_chunk(request, cancel_event=cancel_event)

    with pytest.raises(ConnectionError, match="connection loss"):
        TargetPackageUploader(
            InterruptOnce(),  # type: ignore[arg-type]
            AcceptingVerifier(),
            chunk_size_bytes=64,
        ).upload(package, request_prefix="upload-first")

    resumed = TargetPackageUploader(
        delegate,
        AcceptingVerifier(),
        chunk_size_bytes=64,
    ).upload(package, request_prefix="upload-resume")
    repeated = TargetPackageUploader(
        delegate,
        AcceptingVerifier(),
        chunk_size_bytes=64,
    ).upload(package, request_prefix="upload-repeat")

    assert resumed.manifest_sha256 == manifest.canonical_sha256()
    assert resumed.bytes_resumed > 0
    assert resumed.bytes_uploaded + resumed.bytes_resumed == resumed.bytes_total
    assert repeated.bytes_uploaded == 0
    assert repeated.bytes_resumed == repeated.bytes_total
    uploaded = (
        incoming
        / "packages"
        / manifest.package_id
        / manifest.canonical_sha256()
    )
    assert json.loads((uploaded / "target-package.json").read_text(encoding="utf-8"))
    assert (uploaded / "bin/robotctl").read_bytes() == (package / "bin/robotctl").read_bytes()
    assert not list((incoming / "state").rglob("*.part"))


@pytest.mark.skipif(os.name != "posix", reason="preinstall target protocol is Linux-only")
def test_standalone_preinstall_script_matches_transfer_contract(tmp_path: Path) -> None:
    payload = b"standalone-transfer"
    request = _request(
        operation=TargetPackageTransferOperation.WRITE,
        payload=payload,
    )
    environment = os.environ.copy()
    environment["HOME"] = str(tmp_path)

    completed = subprocess.run(
        [sys.executable, "-c", _PREINSTALL_TRANSFER_SCRIPT],
        input=request.model_dump_json(),
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "SUCCEEDED"
    assert result["request_sha256"] == request.canonical_sha256()
    assert result["complete"] is True
    uploaded = (
        tmp_path
        / ".local/share/rolo/bootstrap/incoming/packages/rolo-target"
        / ("a" * 64)
        / "bin/robotctl"
    )
    assert uploaded.read_bytes() == payload
