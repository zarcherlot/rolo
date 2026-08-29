"""Small dependency-free MCP-compatible JSON-RPC bridge for Rolo.

The bridge deliberately exposes plans and bounded service calls, never arbitrary
shell execution.  It is suitable for Codex/Claude Code MCP configuration and
keeps protocol responses on stdout; diagnostics belong on stderr.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from rolo.commands.lifecycle import run_adapt_start
from rolo.core.config import get_settings
from rolo.job_service import JobService
from rolo.natural_service import NaturalLanguageService
from rolo.stage_agent_read_models import stage_agent_event_page, stage_agent_run_detail
from rolo.stages.adapt.active_discovery import ActiveProbeMode
from rolo.stages.adapt.target_evidence import EvidenceDeploymentMode
from rolo.stages.agent_runner import cancel_stage_run, list_stage_authorization_requests
from rolo.stages.diagnose.service import build_diagnosis_task
from rolo.stages.downstream import DownstreamStageService
from rolo.stages.verify.service import build_verification_task
from rolo.target_ref import LocalTargetRef, parse_target_ref

TOOLS = [
    {
        "name": "rolo_target_inspect",
        "description": "Inspect a local or SSH target without mutation.",
        "inputSchema": {
            "type": "object",
            "properties": {"target": {"type": "string"}},
            "required": ["target"],
        },
    },
    {
        "name": "rolo_bootstrap_plan",
        "description": "Create a deterministic, read-only bootstrap plan for a target.",
        "inputSchema": {
            "type": "object",
            "properties": {"target": {"type": "string"}},
            "required": ["target"],
        },
    },
    {
        "name": "rolo_adapt_start",
        "description": "Run the evidence-backed Adapt journey after same-user confirmation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "robot_id": {"type": "string"},
                "urdf": {"type": "string"},
                "run_agent": {"type": "boolean", "default": True},
                "confirmed": {"type": "boolean", "description": "Explicit current-user approval."},
            },
            "required": ["target", "robot_id"],
        },
    },
    {
        "name": "rolo_diagnose_plan",
        "description": "Prepare a provider-neutral Diagnose Agent task without execution.",
        "inputSchema": {
            "type": "object",
            "properties": {"robot_id": {"type": "string"}},
            "required": ["robot_id"],
        },
    },
    {
        "name": "rolo_verify_plan",
        "description": "Prepare a provider-neutral Verify Agent task without execution.",
        "inputSchema": {
            "type": "object",
            "properties": {"robot_id": {"type": "string"}},
            "required": ["robot_id"],
        },
    },
    {
        "name": "rolo_stage_auth_requests",
        "description": "List pending downstream Stage Agent authorization requests for rolo-vis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string", "enum": ["diagnose", "verify"]},
                "robot_id": {"type": "string"},
            },
        },
    },
    {
        "name": "rolo_stage_run",
        "description": "Read one exact downstream Stage Agent run envelope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string", "enum": ["diagnose", "verify"]},
                "robot_id": {"type": "string"},
                "run_id": {"type": "string"},
            },
            "required": ["stage", "robot_id", "run_id"],
        },
    },
    {
        "name": "rolo_stage_events",
        "description": "Read persisted stdout/stderr events for one exact Stage Agent run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string", "enum": ["diagnose", "verify"]},
                "robot_id": {"type": "string"},
                "run_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                "offset": {"type": "integer", "minimum": 0},
            },
            "required": ["stage", "robot_id", "run_id"],
        },
    },
    {
        "name": "rolo_diagnose_run",
        "description": "Run a configured Diagnose Agent after explicit confirmation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "robot_id": {"type": "string"},
                "confirmed": {"type": "boolean", "description": "Explicit current-user approval."},
                "authorization_ref": {"type": "string"},
            },
            "required": ["robot_id"],
        },
    },
    {
        "name": "rolo_verify_run",
        "description": "Run a configured Verify Agent after explicit confirmation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "robot_id": {"type": "string"},
                "confirmed": {"type": "boolean", "description": "Explicit current-user approval."},
                "authorization_ref": {"type": "string"},
            },
            "required": ["robot_id"],
        },
    },
    {
        "name": "rolo_stage_cancel",
        "description": "Persist cancellation for one exact downstream Stage Agent run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string", "enum": ["diagnose", "verify"]},
                "robot_id": {"type": "string"},
                "run_id": {"type": "string"},
            },
            "required": ["stage", "robot_id", "run_id"],
        },
    },
]


def _result(
    request_id: Any,
    result: Any = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return payload


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _call(name: str, args: dict[str, Any]) -> Any:
    if name == "rolo_stage_cancel":
        stage = str(args.get("stage", "")).strip().lower()
        if stage not in {"diagnose", "verify"}:
            raise ValueError("stage must be diagnose or verify")
        robot_id = str(args.get("robot_id", "")).strip()
        run_id = str(args.get("run_id", "")).strip()
        if not robot_id or not run_id:
            raise ValueError("robot_id and run_id are required")
        return _jsonable(
            cancel_stage_run(get_settings().rolo_artifact_dir, stage, robot_id, run_id)
        )
    if name in {"rolo_stage_run", "rolo_stage_events"}:
        stage = str(args.get("stage", "")).strip().lower()
        if stage not in {"diagnose", "verify"}:
            raise ValueError("stage must be diagnose or verify")
        robot_id = str(args.get("robot_id", "")).strip()
        run_id = str(args.get("run_id", "")).strip()
        if not robot_id or not run_id:
            raise ValueError("robot_id and run_id are required")
        root = get_settings().rolo_artifact_dir
        if name == "rolo_stage_run":
            return _jsonable(stage_agent_run_detail(root, stage, robot_id, run_id))
        return _jsonable(
            stage_agent_event_page(
                root,
                stage,
                robot_id,
                run_id,
                limit=int(args.get("limit", 100)),
                offset=int(args.get("offset", 0)),
            )
        )
    if name in {"rolo_diagnose_run", "rolo_verify_run"}:
        robot_id = str(args.get("robot_id", "")).strip()
        if not robot_id:
            raise ValueError("robot_id is required")
        stage = "diagnose" if name == "rolo_diagnose_run" else "verify"
        return _jsonable(
            DownstreamStageService(get_settings(), stage).run(
                robot_id,
                confirmed=bool(args.get("confirmed", False)),
                authorization_ref=(
                    str(args["authorization_ref"])
                    if args.get("authorization_ref")
                    else None
                ),
            )
        )
    if name == "rolo_stage_auth_requests":
        stage = str(args.get("stage", "")).strip().lower()
        if stage and stage not in {"diagnose", "verify"}:
            raise ValueError("stage must be diagnose or verify")
        robot_id = str(args.get("robot_id", "")).strip()
        settings = get_settings()
        return {
            "requests": list_stage_authorization_requests(
                settings.rolo_artifact_dir,
                stage=stage or None,
                robot_id=robot_id or None,
            )
        }
    if name in {"rolo_diagnose_plan", "rolo_verify_plan"}:
        robot_id = str(args.get("robot_id", "")).strip()
        if not robot_id:
            raise ValueError("robot_id is required")
        settings = get_settings()
        builder = (
            build_diagnosis_task if name == "rolo_diagnose_plan" else build_verification_task
        )
        return _jsonable(
            builder(
                settings.rolo_artifact_dir,
                robot_id,
                provider=settings.coding_agent_provider,
                executor=settings.coding_agent_executor,
                model=settings.coding_agent_model,
            )
        )
    if name in {"rolo_target_inspect", "rolo_bootstrap_plan"}:
        settings = get_settings()
        service = NaturalLanguageService(JobService(settings.rolo_config_dir / "jobs"))
        target = args.get("target")
        if not isinstance(target, str):
            raise ValueError("target is required")
        operation = "检查目标" if name.endswith("inspect") else "生成 bootstrap 计划"
        # Use canonical service dispatch through a parsed intent, avoiding shell.
        from rolo.natural_language import NaturalLanguageIntent, NaturalLanguageOperation

        intent = NaturalLanguageIntent(
            operation=(
                NaturalLanguageOperation.INSPECT
                if name.endswith("inspect")
                else NaturalLanguageOperation.BOOTSTRAP_PLAN
            ),
            target=target,
            source_text=operation,
        )
        return _jsonable(service.execute(intent))
    if name == "rolo_adapt_start":
        target = parse_target_ref(str(args.get("target", "")))
        robot_id = str(args.get("robot_id", "")).strip()
        if not robot_id:
            raise ValueError("robot_id is required")
        if not isinstance(target, LocalTargetRef):
            raise ValueError("MCP Adapt currently requires a local workspace target")
        if not bool(args.get("confirmed", False)):
            return {
                "status": "AUTHORIZATION_REQUIRED",
                "scope": "adapt.run",
                "reason": "Adapt may write local artifacts and invoke the configured Agent.",
                "robot_id": robot_id,
                "project_root": str(target.workspace),
                "resume": {"tool": name, "arguments": {**args, "confirmed": True}},
            }
        settings = get_settings()
        return _jsonable(
            run_adapt_start(
                robot_id=robot_id,
                project_root=target.workspace,
                urdf=Path(args["urdf"]) if args.get("urdf") else None,
                active_probe=ActiveProbeMode.RUNTIME_READONLY,
                run_agent=bool(args.get("run_agent", True)),
                scratch_root=None,
                timeout=None,
                evidence_mode=EvidenceDeploymentMode.LOCAL,
                allow_executable=None,
                collector_descriptor=None,
                verification_secret=None,
                ssh_target=None,
                known_hosts=None,
                collector_config=".rolo/config/target-evidence-collector.json",
                evidence_timeout=45.0,
            )
        )
    raise ValueError(f"unknown tool: {name}")


def handle(message: dict[str, Any]) -> dict[str, Any]:
    request_id = message.get("id")
    method = message.get("method")
    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "rolo", "version": "0.1.0"},
            },
        )
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        try:
            value = _call(str(params.get("name", "")), dict(params.get("arguments") or {}))
            return _result(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(value, ensure_ascii=False, default=str),
                        }
                    ],
                    "structuredContent": value,
                },
            )
        except (OSError, ValueError) as exc:
            return _result(request_id, error={"code": -32000, "message": str(exc)})
    return _result(request_id, error={"code": -32601, "message": f"method not found: {method}"})


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = handle(message)
        except (json.JSONDecodeError, TypeError) as exc:
            response = _result(None, error={"code": -32700, "message": str(exc)})
        sys.stdout.write(json.dumps(response, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
