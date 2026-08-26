from __future__ import annotations

import json
import shlex
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rolo.targets.adapt_jobs import TargetAdaptJobSpecStore
from rolo.targets.bootstrap_jobs import TargetBootstrapJobSpecStore
from rolo.targets.deployment_jobs import DeploymentJobStore, DeploymentRecoveryDisposition
from rolo.targets.models import ApprovalStatus, DeploymentCommandKind, DeploymentJobState
from rolo.targets.project_evidence_jobs import TargetProjectEvidenceJobSpecStore
from rolo.targets.registration import TargetRegistrationService
from rolo.targets.runtime_evidence_jobs import TargetRuntimeEvidenceJobSpecStore
from rolo.targets.runtime_rollback_jobs import TargetRuntimeRollbackJobSpecStore
from rolo.targets.source_discovery_jobs import TargetSourceDiscoveryJobSpecStore


class TargetDeploymentTuiPage(str, Enum):
    FLEET = "fleet"
    TARGET = "target"
    JOB = "job"
    APPROVAL = "approval"
    BLOCKER = "blocker"


class TargetDeploymentTuiField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$")
    value: str = Field(max_length=4096)

    @field_validator("value")
    @classmethod
    def single_line_value(cls, value: str) -> str:
        return " ".join(value.splitlines())


class TargetDeploymentTuiRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: str = Field(min_length=1, max_length=160)
    kind: Literal["TARGET", "JOB", "APPROVAL", "BLOCKER"]
    status: str = Field(min_length=1, max_length=64)
    summary: str = Field(max_length=1000)
    canonical_cli: str | None = Field(default=None, max_length=8192)
    fields: list[TargetDeploymentTuiField] = Field(default_factory=list, max_length=64)

    @field_validator("summary")
    @classmethod
    def single_line_summary(cls, value: str) -> str:
        return " ".join(value.splitlines())


class TargetDeploymentTuiSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-deployment-tui-snapshot/v1"] = (
        "rolo-target-deployment-tui-snapshot/v1"
    )
    page: TargetDeploymentTuiPage
    title: str = Field(min_length=1, max_length=160)
    captured_at: datetime
    rows: list[TargetDeploymentTuiRow] = Field(default_factory=list, max_length=10_000)


class TargetDeploymentWorkbenchSnapshot(BaseModel):
    """Secret-closed GUI read model projected from the same TUI state service."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-deployment-workbench-snapshot/v1"] = (
        "rolo-target-deployment-workbench-snapshot/v1"
    )
    page: TargetDeploymentTuiPage
    title: str = Field(min_length=1, max_length=160)
    captured_at: datetime
    rows: list[TargetDeploymentTuiRow] = Field(default_factory=list, max_length=10_000)


def _canonical_cli(
    command_kind: DeploymentCommandKind,
    *,
    target_id: str,
    idempotency_key: str,
    requested_by: str,
    workspace_root: str | None,
    active_probe: str,
    run_adapter_agent: bool,
    package_ref: str | None = None,
    package_id: str | None = None,
    expected_current_manifest_sha256: str | None = None,
    expected_previous_manifest_sha256: str | None = None,
    approver_principal: str | None = None,
    candidates_json: str | None = None,
    source_scan_roots: list[str] | None = None,
    project_evidence_job_id: str | None = None,
    project_evidence_max_age_s: int | None = None,
    source_discovery_job_id: str | None = None,
    source_discovery_max_age_s: int | None = None,
    runtime_evidence_layers: list[str] | None = None,
    runtime_evidence_job_id: str | None = None,
    runtime_evidence_max_age_s: int | None = None,
) -> str:
    if command_kind == DeploymentCommandKind.ASSESS_CONNECTION:
        argv = [
            "robotctl",
            "target",
            "connect",
            "assess",
            "--target",
            target_id,
            "--active-probe",
            active_probe,
            "--idempotency-key",
            idempotency_key,
            "--requested-by",
            requested_by,
        ]
    elif command_kind == DeploymentCommandKind.BOOTSTRAP and package_ref is not None:
        argv = [
            "robotctl",
            "target",
            "bootstrap",
            "submit",
            "--target",
            target_id,
            "--package-ref",
            package_ref,
            "--approver",
            approver_principal or "<approver>",
            "--idempotency-key",
            idempotency_key,
            "--requested-by",
            requested_by,
        ]
    elif (
        command_kind == DeploymentCommandKind.ROLLBACK_TARGET_RUNTIME
        and package_id is not None
        and expected_current_manifest_sha256 is not None
        and expected_previous_manifest_sha256 is not None
    ):
        argv = [
            "robotctl",
            "target",
            "runtime",
            "rollback",
            "--target",
            target_id,
            "--package-id",
            package_id,
            "--expected-current-manifest-sha256",
            expected_current_manifest_sha256,
            "--expected-previous-manifest-sha256",
            expected_previous_manifest_sha256,
            "--approver",
            approver_principal or "<approver>",
            "--idempotency-key",
            idempotency_key,
            "--requested-by",
            requested_by,
        ]
    elif command_kind == DeploymentCommandKind.COLLECT_EVIDENCE and candidates_json is not None:
        argv = [
            "robotctl",
            "target",
            "project-evidence",
            "submit",
            "--target",
            target_id,
            "--candidates-json",
            candidates_json,
            "--approver",
            approver_principal or "<approver>",
            "--idempotency-key",
            idempotency_key,
            "--requested-by",
            requested_by,
        ]
    elif command_kind == DeploymentCommandKind.COLLECT_EVIDENCE and source_scan_roots is not None:
        argv = [
            "robotctl",
            "target",
            "source-discovery",
            "submit",
            "--target",
            target_id,
            "--approver",
            approver_principal or "<approver>",
            "--idempotency-key",
            idempotency_key,
            "--requested-by",
            requested_by,
        ]
        for root in source_scan_roots:
            argv.extend(("--scan-root", root))
    elif (
        command_kind == DeploymentCommandKind.COLLECT_EVIDENCE
        and runtime_evidence_layers is not None
    ):
        argv = [
            "robotctl",
            "target",
            "runtime-evidence",
            "submit",
            "--target",
            target_id,
            "--approver",
            approver_principal or "<approver>",
            "--idempotency-key",
            idempotency_key,
            "--requested-by",
            requested_by,
        ]
    elif command_kind == DeploymentCommandKind.ADAPT and workspace_root is not None:
        argv = [
            "robotctl",
            "target",
            "adapt",
            "submit",
            "--target",
            target_id,
            "--active-probe",
            active_probe,
            "--idempotency-key",
            idempotency_key,
            "--requested-by",
            requested_by,
        ]
        argv.append("--run-adapter-agent" if run_adapter_agent else "--no-run-adapter-agent")
        if project_evidence_job_id is not None:
            argv.extend(("--project-evidence-job-id", project_evidence_job_id))
            if project_evidence_max_age_s is not None:
                argv.extend(
                    (
                        "--project-evidence-max-age-s",
                        str(project_evidence_max_age_s),
                    )
                )
        if source_discovery_job_id is not None:
            argv.extend(("--source-discovery-job-id", source_discovery_job_id))
            if source_discovery_max_age_s is not None:
                argv.extend(
                    (
                        "--source-discovery-max-age-s",
                        str(source_discovery_max_age_s),
                    )
                )
        if runtime_evidence_job_id is not None:
            argv.extend(("--runtime-evidence-job-id", runtime_evidence_job_id))
            if runtime_evidence_max_age_s is not None:
                argv.extend(
                    (
                        "--runtime-evidence-max-age-s",
                        str(runtime_evidence_max_age_s),
                    )
                )
    else:
        return ""
    return shlex.join(argv)


class TargetDeploymentTui:
    """Read-only terminal workbench over the same Target/Job/Approval stores as API/CLI."""

    def __init__(
        self,
        registrations: TargetRegistrationService,
        jobs: DeploymentJobStore,
        specs: TargetBootstrapJobSpecStore,
        rollback_specs: TargetRuntimeRollbackJobSpecStore | None = None,
        project_evidence_specs: TargetProjectEvidenceJobSpecStore | None = None,
        adapt_specs: TargetAdaptJobSpecStore | None = None,
        source_discovery_specs: TargetSourceDiscoveryJobSpecStore | None = None,
        runtime_evidence_specs: TargetRuntimeEvidenceJobSpecStore | None = None,
    ) -> None:
        self.registrations = registrations
        self.jobs = jobs
        self.specs = specs
        self.rollback_specs = rollback_specs
        self.project_evidence_specs = project_evidence_specs
        self.adapt_specs = adapt_specs
        self.source_discovery_specs = source_discovery_specs
        self.runtime_evidence_specs = runtime_evidence_specs

    def _job_row(self, job_id: str) -> TargetDeploymentTuiRow:
        record = self.jobs.load_job(job_id)
        command = record.job.command
        package_ref = None
        package_id = None
        current_manifest_sha256 = None
        previous_manifest_sha256 = None
        approver = None
        candidates_json = None
        source_scan_roots = None
        project_evidence_job_id = None
        project_evidence_max_age_s = None
        source_discovery_job_id = None
        source_discovery_max_age_s = None
        runtime_evidence_layers = None
        runtime_evidence_job_id = None
        runtime_evidence_max_age_s = None
        if command.command == DeploymentCommandKind.BOOTSTRAP:
            try:
                spec = self.specs.load(job_id)
            except ValueError:
                spec = None
            if spec is not None:
                package_ref = f"{spec.package_id}@{spec.manifest_sha256}"
                approver = spec.approver_principal
        elif (
            command.command == DeploymentCommandKind.ROLLBACK_TARGET_RUNTIME
            and self.rollback_specs is not None
        ):
            try:
                rollback_spec = self.rollback_specs.load(job_id)
            except ValueError:
                rollback_spec = None
            if rollback_spec is not None:
                package_id = rollback_spec.package_id
                current_manifest_sha256 = rollback_spec.expected_current_manifest_sha256
                previous_manifest_sha256 = rollback_spec.expected_previous_manifest_sha256
                approver = rollback_spec.approver_principal
        elif command.command == DeploymentCommandKind.COLLECT_EVIDENCE and (
            self.project_evidence_specs is not None
            or self.source_discovery_specs is not None
            or self.runtime_evidence_specs is not None
        ):
            project_evidence_spec = (
                self.project_evidence_specs.load(job_id)
                if self.project_evidence_specs is not None
                and self.project_evidence_specs.contains(job_id)
                else None
            )
            if project_evidence_spec is not None:
                approver = project_evidence_spec.approver_principal
                candidates_json = json.dumps(
                    [
                        candidate.model_dump(mode="json")
                        for candidate in project_evidence_spec.candidates
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            elif self.source_discovery_specs is not None and self.source_discovery_specs.contains(
                job_id
            ):
                source_spec = self.source_discovery_specs.load(job_id)
                approver = source_spec.approver_principal
                source_scan_roots = source_spec.scan_roots
            elif self.runtime_evidence_specs is not None and self.runtime_evidence_specs.contains(
                job_id
            ):
                runtime_spec = self.runtime_evidence_specs.load(job_id)
                approver = runtime_spec.approver_principal
                runtime_evidence_layers = (
                    runtime_spec.collection_request.evidence_request.requested_layers
                )
        elif command.command == DeploymentCommandKind.ADAPT and self.adapt_specs is not None:
            try:
                adapt_spec = self.adapt_specs.load(job_id)
            except ValueError:
                adapt_spec = None
            if adapt_spec is not None and adapt_spec.project_evidence is not None:
                project_evidence_job_id = adapt_spec.project_evidence.job_id
                project_evidence_max_age_s = int(
                    (
                        adapt_spec.project_evidence.expires_at
                        - adapt_spec.project_evidence.observed_at
                    ).total_seconds()
                )
            if adapt_spec is not None and adapt_spec.source_discovery is not None:
                source_discovery_job_id = adapt_spec.source_discovery.job_id
                source_discovery_max_age_s = int(
                    (
                        adapt_spec.source_discovery.expires_at
                        - adapt_spec.source_discovery.observed_at
                    ).total_seconds()
                )
            if adapt_spec is not None and adapt_spec.runtime_evidence is not None:
                runtime_evidence_job_id = adapt_spec.runtime_evidence.job_id
                runtime_evidence_max_age_s = int(
                    (
                        adapt_spec.runtime_evidence.expires_at
                        - adapt_spec.runtime_evidence.collected_at
                    ).total_seconds()
                )
        canonical = _canonical_cli(
            command.command,
            target_id=command.target_id,
            idempotency_key=command.idempotency_key,
            requested_by=command.requested_by,
            workspace_root=command.workspace_root,
            active_probe=command.active_probe,
            run_adapter_agent=command.run_adapter_agent,
            package_ref=package_ref,
            package_id=package_id,
            expected_current_manifest_sha256=current_manifest_sha256,
            expected_previous_manifest_sha256=previous_manifest_sha256,
            approver_principal=approver,
            candidates_json=candidates_json,
            source_scan_roots=source_scan_roots,
            project_evidence_job_id=project_evidence_job_id,
            project_evidence_max_age_s=project_evidence_max_age_s,
            source_discovery_job_id=source_discovery_job_id,
            source_discovery_max_age_s=source_discovery_max_age_s,
            runtime_evidence_layers=runtime_evidence_layers,
            runtime_evidence_job_id=runtime_evidence_job_id,
            runtime_evidence_max_age_s=runtime_evidence_max_age_s,
        )
        summary = (
            "; ".join(record.job.blockers)
            if record.job.blockers
            else f"{command.command.value} attempt {record.attempt}"
        )
        return TargetDeploymentTuiRow(
            identity=job_id,
            kind="JOB",
            status=record.job.state.value,
            summary=summary,
            canonical_cli=canonical or None,
            fields=[
                TargetDeploymentTuiField(name="target", value=command.target_id),
                TargetDeploymentTuiField(name="recovery", value=record.recovery_disposition.value),
                TargetDeploymentTuiField(
                    name="updated_at", value=record.job.updated_at.isoformat()
                ),
                TargetDeploymentTuiField(name="command_sha256", value=record.job.command_sha256),
            ],
        )

    def _approval_row(
        self,
        approval_id: str,
        *,
        captured_at: datetime,
    ) -> TargetDeploymentTuiRow:
        request = self.jobs.load_approval_request(approval_id)
        decision = self.jobs.get_approval_decision(approval_id)
        status = (
            decision.status
            if decision is not None
            else (
                ApprovalStatus.EXPIRED
                if captured_at >= request.expires_at
                else ApprovalStatus.PENDING
            )
        )
        job = self.jobs.load_job(request.job_id)
        profile = self.registrations.load(request.target_id).target
        approval_fields = [
            TargetDeploymentTuiField(name="target", value=request.target_id),
            TargetDeploymentTuiField(name="action", value=request.action.value),
            TargetDeploymentTuiField(name="risk", value=request.risk),
            TargetDeploymentTuiField(name="desired_version", value=profile.desired_rolo_version),
            TargetDeploymentTuiField(
                name="workspace", value=job.job.command.workspace_root or "NOT_APPLICABLE"
            ),
            TargetDeploymentTuiField(name="command_sha256", value=request.command_sha256),
            TargetDeploymentTuiField(name="requester", value=request.requester_principal),
            TargetDeploymentTuiField(name="approver", value=request.approver_principal),
            TargetDeploymentTuiField(name="expires_at", value=request.expires_at.isoformat()),
            TargetDeploymentTuiField(
                name="scope_sha256",
                value=request.authorization_scope_sha256 or "NOT_BOUND",
            ),
        ]
        if job.job.command.command == DeploymentCommandKind.BOOTSTRAP:
            try:
                spec = self.specs.load(job.job.job_id)
            except ValueError:
                spec = None
            if spec is not None:
                approval_fields.extend(
                    [
                        TargetDeploymentTuiField(
                            name="package_ref",
                            value=f"{spec.package_id}@{spec.manifest_sha256}",
                        ),
                        TargetDeploymentTuiField(
                            name="manifest_sha256", value=spec.manifest_sha256
                        ),
                    ]
                )
        elif (
            job.job.command.command == DeploymentCommandKind.ROLLBACK_TARGET_RUNTIME
            and self.rollback_specs is not None
        ):
            try:
                rollback_spec = self.rollback_specs.load(job.job.job_id)
            except ValueError:
                rollback_spec = None
            if rollback_spec is not None:
                approval_fields.extend(
                    [
                        TargetDeploymentTuiField(name="package_id", value=rollback_spec.package_id),
                        TargetDeploymentTuiField(
                            name="expected_current_manifest_sha256",
                            value=(rollback_spec.expected_current_manifest_sha256),
                        ),
                        TargetDeploymentTuiField(
                            name="expected_previous_manifest_sha256",
                            value=(rollback_spec.expected_previous_manifest_sha256),
                        ),
                    ]
                )
        elif job.job.command.command == DeploymentCommandKind.COLLECT_EVIDENCE and (
            self.project_evidence_specs is not None
            or self.source_discovery_specs is not None
            or self.runtime_evidence_specs is not None
        ):
            project_evidence_spec = (
                self.project_evidence_specs.load(job.job.job_id)
                if self.project_evidence_specs is not None
                and self.project_evidence_specs.contains(job.job.job_id)
                else None
            )
            if project_evidence_spec is not None:
                approval_fields.extend(
                    [
                        TargetDeploymentTuiField(
                            name="candidate_count",
                            value=str(len(project_evidence_spec.candidates)),
                        ),
                        TargetDeploymentTuiField(
                            name="workspace_sha256",
                            value=project_evidence_spec.workspace.canonical_sha256(),
                        ),
                    ]
                )
            elif self.source_discovery_specs is not None and self.source_discovery_specs.contains(
                job.job.job_id
            ):
                source_spec = self.source_discovery_specs.load(job.job.job_id)
                approval_fields.extend(
                    [
                        TargetDeploymentTuiField(
                            name="scan_root_count",
                            value=str(len(source_spec.scan_roots)),
                        ),
                        TargetDeploymentTuiField(
                            name="workspace_sha256",
                            value=source_spec.workspace.canonical_sha256(),
                        ),
                    ]
                )
            elif self.runtime_evidence_specs is not None and self.runtime_evidence_specs.contains(
                job.job.job_id
            ):
                runtime_spec = self.runtime_evidence_specs.load(job.job.job_id)
                approval_fields.extend(
                    [
                        TargetDeploymentTuiField(
                            name="requested_layers",
                            value=",".join(
                                runtime_spec.collection_request.evidence_request.requested_layers
                            ),
                        ),
                        TargetDeploymentTuiField(
                            name="collector_descriptor_sha256",
                            value=runtime_spec.collector_descriptor_sha256,
                        ),
                        TargetDeploymentTuiField(
                            name="evidence_expires_at",
                            value=runtime_spec.approval_expires_at.isoformat(),
                        ),
                    ]
                )
        return TargetDeploymentTuiRow(
            identity=approval_id,
            kind="APPROVAL",
            status=status.value,
            summary=request.sanitized_summary,
            canonical_cli=shlex.join(
                [
                    "robotctl",
                    "target",
                    "approval",
                    "decide",
                    "--approval-id",
                    approval_id,
                    "--principal",
                    request.approver_principal,
                    "--idempotency-key",
                    "<idempotency-key>",
                    "--reason",
                    "<review-reason>",
                    "--approve",
                ]
            ),
            fields=approval_fields,
        )

    def snapshot(
        self,
        page: TargetDeploymentTuiPage,
        *,
        target_id: str | None = None,
        job_id: str | None = None,
        approval_id: str | None = None,
        limit: int = 100,
        now: datetime | None = None,
    ) -> TargetDeploymentTuiSnapshot:
        if not 1 <= limit <= 1000:
            raise ValueError("TUI page limit is out of bounds")
        captured_at = now or datetime.now(timezone.utc)
        rows: list[TargetDeploymentTuiRow]
        if page == TargetDeploymentTuiPage.FLEET:
            jobs = self.jobs.list_jobs(limit=1000)
            rows = []
            for profile in self.registrations.registry.list_targets()[:limit]:
                target_jobs = [
                    item for item in jobs if item.job.command.target_id == profile.target_id
                ]
                latest = max(target_jobs, key=lambda item: item.job.updated_at, default=None)
                rows.append(
                    TargetDeploymentTuiRow(
                        identity=profile.target_id,
                        kind="TARGET",
                        status=latest.job.state.value if latest else "REGISTERED",
                        summary=(
                            f"{profile.transport.value} target; {len(target_jobs)} persistent jobs"
                        ),
                        fields=[
                            TargetDeploymentTuiField(
                                name="workspace", value=profile.workspace_root
                            ),
                            TargetDeploymentTuiField(
                                name="desired_version", value=profile.desired_rolo_version
                            ),
                        ],
                    )
                )
            title = "Fleet"
        elif page == TargetDeploymentTuiPage.TARGET:
            if target_id is None:
                raise ValueError("target TUI page requires target_id")
            registration = self.registrations.load(target_id)
            profile = registration.target
            rows = [
                TargetDeploymentTuiRow(
                    identity=target_id,
                    kind="TARGET",
                    status="REGISTERED",
                    summary=f"{profile.transport.value} / {profile.trust_level.value}",
                    fields=[
                        TargetDeploymentTuiField(name="workspace", value=profile.workspace_root),
                        TargetDeploymentTuiField(
                            name="desired_version", value=profile.desired_rolo_version
                        ),
                        TargetDeploymentTuiField(
                            name="release_key_id",
                            value=profile.release_signing_key_id or "NOT_CONFIGURED",
                        ),
                    ],
                )
            ]
            if registration.connection is not None:
                connection = registration.connection
                rows[0].fields.extend(
                    [
                        TargetDeploymentTuiField(name="ssh_host", value=connection.host),
                        TargetDeploymentTuiField(name="ssh_port", value=str(connection.port)),
                        TargetDeploymentTuiField(name="ssh_user", value=connection.user),
                        TargetDeploymentTuiField(
                            name="ssh_fingerprint",
                            value=connection.expected_host_key_sha256 or "SSH_CA",
                        ),
                    ]
                )
            rows.extend(
                self._job_row(item.job.job_id)
                for item in self.jobs.list_jobs(limit=1000)
                if item.job.command.target_id == target_id
            )
            rows = rows[:limit]
            title = f"Target {target_id}"
        elif page == TargetDeploymentTuiPage.JOB:
            if job_id is None:
                raise ValueError("job TUI page requires job_id")
            rows = [self._job_row(job_id)]
            title = f"Job {job_id}"
        elif page == TargetDeploymentTuiPage.APPROVAL:
            approval_ids = (
                [approval_id]
                if approval_id is not None
                else [
                    request.approval_id for request in self.jobs.list_approval_requests(limit=limit)
                ]
            )
            rows = [self._approval_row(item, captured_at=captured_at) for item in approval_ids]
            title = f"Approval {approval_id}" if approval_id is not None else "Approvals"
        else:
            blocked_states = {DeploymentJobState.BLOCKED, DeploymentJobState.FAILED}
            rows = []
            for item in self.jobs.list_jobs(limit=1000):
                if (
                    item.job.state not in blocked_states
                    and item.recovery_disposition == DeploymentRecoveryDisposition.NONE
                    and not item.job.blockers
                ):
                    continue
                job_row = self._job_row(item.job.job_id)
                rows.append(
                    job_row.model_copy(
                        update={
                            "kind": "BLOCKER",
                            "summary": job_row.summary or "Deployment requires attention.",
                        }
                    )
                )
            rows = rows[:limit]
            title = "Blockers and recovery"
        return TargetDeploymentTuiSnapshot(
            page=page,
            title=title,
            captured_at=captured_at,
            rows=rows,
        )

    def workbench_snapshot(
        self,
        page: TargetDeploymentTuiPage,
        **kwargs: object,
    ) -> TargetDeploymentWorkbenchSnapshot:
        snapshot = self.snapshot(page, **kwargs)
        return TargetDeploymentWorkbenchSnapshot(
            page=snapshot.page,
            title=snapshot.title,
            captured_at=snapshot.captured_at,
            rows=snapshot.rows,
        )


def render_target_deployment_tui(snapshot: TargetDeploymentTuiSnapshot) -> str:
    lines = [
        f"Rolo Deployment Workbench | {snapshot.title}",
        f"Captured {snapshot.captured_at.isoformat()}",
        "",
    ]
    if not snapshot.rows:
        lines.append("No records.")
        return "\n".join(lines) + "\n"
    identity_width = min(42, max(8, *(len(row.identity) for row in snapshot.rows)))
    lines.append(f"{'IDENTITY':<{identity_width}}  {'KIND':<8}  {'STATUS':<24}  SUMMARY")
    lines.append("-" * min(120, identity_width + 76))
    for row in snapshot.rows:
        identity = row.identity[:identity_width]
        lines.append(
            f"{identity:<{identity_width}}  {row.kind:<8}  {row.status:<24}  {row.summary}"
        )
        for field in row.fields:
            lines.append(f"  {field.name}: {field.value}")
        if row.canonical_cli:
            lines.append(f"  canonical_cli: {row.canonical_cli}")
    return "\n".join(lines) + "\n"
