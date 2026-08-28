"""Deterministic, bounded natural-language intent mapping for the product entrypoint."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NaturalLanguageOperation(str, Enum):
    ADAPT_START = "adapt.start"
    INSPECT = "target.inspect"
    BOOTSTRAP_PLAN = "target.bootstrap-plan"
    BOOTSTRAP_REQUEST = "target.bootstrap-request"
    BOOTSTRAP_APPROVE = "target.bootstrap-approve"
    BOOTSTRAP_EXECUTE = "target.bootstrap-execute"
    JOB_RECOVER = "job.recover"
    DIAGNOSE_PLAN = "diagnose.plan"
    VERIFY_PLAN = "verify.plan"
    DIAGNOSE_RUN = "diagnose.run"
    VERIFY_RUN = "verify.run"


class NaturalLanguageIntent(BaseModel):
    schema_version: str = "rolo-natural-language-intent/v1"
    operation: NaturalLanguageOperation
    target: str | None = Field(default=None, max_length=1024)
    robot_id: str | None = Field(default=None, max_length=128)
    urdf: str | None = Field(default=None, max_length=1024)
    run_agent: bool = True
    plan_file: str | None = None
    request_file: str | None = None
    decision_file: str | None = None
    manifest_file: str | None = None
    package_file: str | None = None
    verification_key_file: str | None = None
    known_hosts_file: str | None = None
    execute: bool = False
    confirmed: bool = False
    authorization_ref: str | None = None
    job_id: str | None = None
    actor: str | None = None
    source_text: str = Field(min_length=1, max_length=2000)
    limitations: list[str] = Field(default_factory=list)


class NaturalLanguageExecutionAdapter:
    """Dispatch parsed intents only to explicitly registered canonical handlers."""

    def __init__(self, handlers: Mapping[NaturalLanguageOperation, Callable[..., Any]]) -> None:
        self._handlers = dict(handlers)

    def dispatch(self, intent: NaturalLanguageIntent) -> Any:
        handler = self._handlers.get(intent.operation)
        if handler is None:
            raise ValueError(f"no handler registered for {intent.operation.value}")
        if intent.operation in {
            NaturalLanguageOperation.BOOTSTRAP_REQUEST,
            NaturalLanguageOperation.BOOTSTRAP_APPROVE,
        } and not intent.actor:
            raise ValueError("approval intents require an explicit actor")
        return handler(intent)


_TARGET = r"(ssh://[^\s，。,；;]+|(?:[A-Za-z]:[\\/]|/)[^\s，。,；;]+)"
_WORKSPACE_TARGET = r"(ssh://[^\s，。,；;]+|(?:[A-Za-z]:[\\/]|/|\./|\.\./)[^\s，。,；;]+)"


def parse_natural_language(text: str) -> NaturalLanguageIntent:
    """Map only explicit, known phrases; refuse ambiguous or executable text."""
    source = text.strip()
    if not source or len(source) > 2000:
        raise ValueError("natural-language request must contain 1..2000 characters")
    if any(token in source for token in ("&&", "||", ";", "|", "`", "$(", "<", ">")):
        raise ValueError("natural-language request contains unsupported command syntax")
    match = re.search(
        rf"(?:适配|adapt)\s*(?:目标|工作区|workspace)?\s*{_WORKSPACE_TARGET}",
        source,
        re.IGNORECASE,
    )
    if match:
        target = match.group(1)
        robot_match = re.search(
            r"(?:机器人(?:叫|是)?|--robot(?:-id)?|"
            r"(?<![A-Za-z0-9_.-])robot(?:-id)?(?![A-Za-z0-9_.-]))"
            r"\s*[:：=]?\s*([A-Za-z0-9_.:-]+)",
            source,
            re.IGNORECASE,
        )
        if robot_match is None:
            raise ValueError("Adapt request requires an explicit robot id")
        urdf_match = re.search(
            rf"(?:urdf)\s*(?:为|是|[:：=])?\s*{_WORKSPACE_TARGET}",
            source,
            re.IGNORECASE,
        )
        return NaturalLanguageIntent(
            operation=NaturalLanguageOperation.ADAPT_START,
            target=target,
            robot_id=robot_match.group(1),
            urdf=urdf_match.group(1) if urdf_match else None,
            run_agent=not bool(
                re.search(
                    r"(?:只|仅|先)?\s*(?:做)?\s*"
                    r"(?:发现|discovery\s*only|--discover-only)",
                    source,
                    re.IGNORECASE,
                )
            ),
            source_text=source,
        )
    match = re.search(
        rf"(?:检查|inspect)\s*(?:目标|target)?\s*{_TARGET}", source, re.IGNORECASE
    )
    if match:
        return NaturalLanguageIntent(
            operation=NaturalLanguageOperation.INSPECT,
            target=match.group(1),
            source_text=source,
        )
    match = re.search(
        r"(?:申请|请求|request)\s*(?:bootstrap\s*)?(?:审批|approval)\s*([^\s，。,；;]+)",
        source,
        re.IGNORECASE,
    )
    if match:
        return NaturalLanguageIntent(
            operation=NaturalLanguageOperation.BOOTSTRAP_REQUEST,
            plan_file=match.group(1),
            actor=_actor(source),
            source_text=source,
        )
    match = re.search(
        r"(?:批准|同意|approve)\s*(?:bootstrap\s*)?(?:计划\s*)?([^\s，。,；;]+)\s+([^\s，。,；;]+)",
        source,
        re.IGNORECASE,
    )
    if match:
        return NaturalLanguageIntent(
            operation=NaturalLanguageOperation.BOOTSTRAP_APPROVE,
            plan_file=match.group(1),
            request_file=match.group(2),
            actor=_actor(source),
            source_text=source,
        )
    match = re.search(
        r"(?:执行|execute)\s+bootstrap\s+(.+)$",
        source,
        re.IGNORECASE,
    )
    if match:
        parts = match.group(1).split()
        execute = False
        if parts and parts[-1] == "--execute":
            execute = True
            parts.pop()
        if len(parts) != 7:
            raise ValueError(
                "bootstrap execute requires plan, request, decision, manifest, "
                "package, key and known_hosts files"
            )
        return NaturalLanguageIntent(
            operation=NaturalLanguageOperation.BOOTSTRAP_EXECUTE,
            plan_file=parts[0],
            request_file=parts[1],
            decision_file=parts[2],
            manifest_file=parts[3],
            package_file=parts[4],
            verification_key_file=parts[5],
            known_hosts_file=parts[6],
            execute=execute,
            source_text=source,
        )
    match = re.search(
        rf"(?:生成|创建|create)\s*(?:bootstrap\s*)?(?:计划|plan)\s*{_TARGET}",
        source,
        re.IGNORECASE,
    )
    if match:
        return NaturalLanguageIntent(
            operation=NaturalLanguageOperation.BOOTSTRAP_PLAN,
            target=match.group(1),
            source_text=source,
        )
    match = re.search(
        r"(?:恢复|recover|resume)\s*(?:任务|job)?\s*(job_[0-9a-f]+)",
        source,
        re.IGNORECASE,
    )
    if match:
        return NaturalLanguageIntent(
            operation=NaturalLanguageOperation.JOB_RECOVER,
            job_id=match.group(1),
            source_text=source,
        )
    match = re.search(
        rf"(?:执行|run)\s*(?:诊断|diagnose)\s*{_TARGET}", source, re.IGNORECASE
    )
    if match:
        return NaturalLanguageIntent(
            operation=NaturalLanguageOperation.DIAGNOSE_RUN,
            target=match.group(1),
            robot_id=_robot_id(source),
            source_text=source,
        )
    match = re.search(
        rf"(?:诊断|diagnose)\s*(?:计划|plan)?\s*{_TARGET}", source, re.IGNORECASE
    )
    if match:
        return NaturalLanguageIntent(
            operation=NaturalLanguageOperation.DIAGNOSE_PLAN,
            target=match.group(1),
            robot_id=_robot_id(source),
            source_text=source,
        )
    match = re.search(
        rf"(?:执行|run)\s*(?:验证|verify)\s*{_TARGET}", source, re.IGNORECASE
    )
    if match:
        return NaturalLanguageIntent(
            operation=NaturalLanguageOperation.VERIFY_RUN,
            target=match.group(1),
            robot_id=_robot_id(source),
            source_text=source,
        )
    match = re.search(
        rf"(?:验证|verify)\s*(?:计划|plan)?\s*{_TARGET}", source, re.IGNORECASE
    )
    if match:
        return NaturalLanguageIntent(
            operation=NaturalLanguageOperation.VERIFY_PLAN,
            target=match.group(1),
            robot_id=_robot_id(source),
            source_text=source,
        )
    raise ValueError("unsupported or ambiguous natural-language request")


def _actor(source: str) -> str | None:
    match = re.search(r"(?:由|by|as)\s*([A-Za-z0-9_.:-]+)", source, re.IGNORECASE)
    return match.group(1) if match else None


def _robot_id(source: str) -> str | None:
    match = re.search(
        r"(?:机器人(?:叫|是)?|--robot(?:-id)?|(?<![A-Za-z0-9_.-])robot(?:-id)?(?![A-Za-z0-9_.-]))"
        r"\s*[:：=]?\s*([A-Za-z0-9_.:-]+)",
        source,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def intent_to_argv(intent: NaturalLanguageIntent) -> list[str]:
    """Return the canonical product CLI argv; this function never executes it."""
    if intent.operation == NaturalLanguageOperation.ADAPT_START:
        if not intent.target or not intent.robot_id:
            raise ValueError("Adapt intent requires target and robot_id")
        argv = ["adapt", intent.target, "--robot", intent.robot_id]
        if intent.urdf:
            argv.extend(["--urdf", intent.urdf])
        if not intent.run_agent:
            argv.append("--discover-only")
        return argv
    if intent.operation == NaturalLanguageOperation.INSPECT:
        return ["target", "inspect", intent.target or ""]
    if intent.operation == NaturalLanguageOperation.BOOTSTRAP_PLAN:
        return ["target", "bootstrap-plan", intent.target or ""]
    if intent.operation == NaturalLanguageOperation.BOOTSTRAP_REQUEST:
        if not intent.plan_file or not intent.actor:
            raise ValueError("bootstrap request intent requires plan_file and actor")
        return [
            "target",
            "bootstrap-request",
            intent.plan_file or "",
            "--requested-by",
            intent.actor or "",
        ]
    if intent.operation == NaturalLanguageOperation.BOOTSTRAP_APPROVE:
        if not intent.plan_file or not intent.request_file or not intent.actor:
            raise ValueError("bootstrap approval intent requires plan_file, request_file and actor")
        return [
            "target",
            "bootstrap-approve",
            intent.plan_file or "",
            intent.request_file or "",
            "--approved-by",
            intent.actor or "",
        ]
    if intent.operation == NaturalLanguageOperation.BOOTSTRAP_EXECUTE:
        required = (
            intent.plan_file,
            intent.request_file,
            intent.decision_file,
            intent.manifest_file,
            intent.package_file,
            intent.verification_key_file,
            intent.known_hosts_file,
        )
        if any(value is None for value in required):
            raise ValueError("bootstrap execute intent requires all input files")
        argv = [
            "target",
            "bootstrap-execute",
            intent.plan_file or "",
            intent.request_file or "",
            intent.decision_file or "",
            "--manifest",
            intent.manifest_file or "",
            "--package",
            intent.package_file or "",
            "--verification-key-file",
            intent.verification_key_file or "",
            "--known-hosts",
            intent.known_hosts_file or "",
        ]
        if intent.execute:
            argv.append("--execute")
        return argv
    if intent.operation == NaturalLanguageOperation.JOB_RECOVER:
        return ["job", "recover", intent.job_id or ""]
    if intent.operation == NaturalLanguageOperation.DIAGNOSE_PLAN:
        if not intent.target or not intent.robot_id:
            raise ValueError("diagnose plan intent requires target and robot_id")
        return ["diagnose", "plan", "--robot", intent.robot_id]
    if intent.operation == NaturalLanguageOperation.VERIFY_PLAN:
        if not intent.target or not intent.robot_id:
            raise ValueError("verify plan intent requires target and robot_id")
        return ["verify", "plan", "--robot", intent.robot_id]
    if intent.operation == NaturalLanguageOperation.DIAGNOSE_RUN:
        if not intent.target or not intent.robot_id:
            raise ValueError("diagnose run intent requires target and robot_id")
        argv = ["diagnose", "run", "--robot", intent.robot_id]
        if intent.authorization_ref:
            argv.extend(["--authorization-ref", intent.authorization_ref])
        return argv
    if intent.operation == NaturalLanguageOperation.VERIFY_RUN:
        if not intent.target or not intent.robot_id:
            raise ValueError("verify run intent requires target and robot_id")
        argv = ["verify", "run", "--robot", intent.robot_id]
        if intent.authorization_ref:
            argv.extend(["--authorization-ref", intent.authorization_ref])
        return argv
    raise ValueError(f"unsupported intent operation: {intent.operation}")
