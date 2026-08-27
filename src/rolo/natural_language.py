"""Deterministic, bounded natural-language intent mapping for the product entrypoint."""

from __future__ import annotations

import re
from enum import Enum

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
