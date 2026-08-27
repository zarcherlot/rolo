"""Deterministic, bounded natural-language intent mapping for the product entrypoint."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NaturalLanguageOperation(str, Enum):
    INSPECT = "target.inspect"
    BOOTSTRAP_PLAN = "target.bootstrap-plan"
    BOOTSTRAP_REQUEST = "target.bootstrap-request"
    BOOTSTRAP_APPROVE = "target.bootstrap-approve"
    JOB_RECOVER = "job.recover"


class NaturalLanguageIntent(BaseModel):
    schema_version: str = "rolo-natural-language-intent/v1"
    operation: NaturalLanguageOperation
    target: str | None = Field(default=None, max_length=1024)
    plan_file: str | None = None
    request_file: str | None = None
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


def parse_natural_language(text: str) -> NaturalLanguageIntent:
    """Map only explicit, known phrases; refuse ambiguous or executable text."""
    source = text.strip()
    if not source or len(source) > 2000:
        raise ValueError("natural-language request must contain 1..2000 characters")
    if any(token in source for token in ("&&", "||", ";", "|", "`", "$(", "<", ">")):
        raise ValueError("natural-language request contains unsupported command syntax")
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
    raise ValueError("unsupported or ambiguous natural-language request")


def _actor(source: str) -> str | None:
    match = re.search(r"(?:由|by|as)\s*([A-Za-z0-9_.:-]+)", source, re.IGNORECASE)
    return match.group(1) if match else None


def intent_to_argv(intent: NaturalLanguageIntent) -> list[str]:
    """Return the canonical product CLI argv; this function never executes it."""
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
    if intent.operation == NaturalLanguageOperation.JOB_RECOVER:
        return ["job", "recover", intent.job_id or ""]
    raise ValueError(f"unsupported intent operation: {intent.operation}")
