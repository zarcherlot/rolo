"""Interactive natural-language console for the product CLI."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import TextIO

from rolo.core.config import get_settings
from rolo.job_service import JobService
from rolo.natural_language import (
    NaturalLanguageOperation,
    intent_to_argv,
    parse_natural_language,
)
from rolo.natural_service import NaturalLanguageService
from rolo.query_adapter import ServiceJobQueryAdapter
from rolo.ui_models import JobUiAdapter


class RoloConsole:
    """Codex-like REPL with explicit plans and confirmation for mutations."""

    def __init__(
        self,
        service: NaturalLanguageService,
        adapter: JobUiAdapter,
        *,
        input_stream: TextIO | None = None,
        output_stream: TextIO | None = None,
        confirm: Callable[[str], bool] | None = None,
    ) -> None:
        self.service = service
        self.adapter = adapter
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.confirm = confirm

    def run(self) -> None:
        input_stream = self.input_stream or sys.stdin
        output_stream = self.output_stream or sys.stdout
        self._write(output_stream, "Rolo — natural-language console")
        self._write(
            output_stream,
            "Describe a target or operation. Commands: /help, /jobs, /show JOB_ID, "
            "/events JOB_ID, /quit",
        )
        while True:
            self._write(output_stream, "rolo> ", end="")
            line = input_stream.readline()
            if not line:
                return
            request = line.strip()
            if not request:
                continue
            if self._command(request, output_stream):
                return
            self._handle_request(request, input_stream, output_stream)

    def _command(self, request: str, output_stream: TextIO) -> bool:
        command, _, argument = request.partition(" ")
        command = command.casefold()
        if command in {"/quit", "/exit", "quit", "exit"}:
            self._write(output_stream, "bye")
            return True
        if command in {"/help", "help"}:
            self._write(
                output_stream,
                "/help | /jobs | /show JOB_ID | /events JOB_ID | /quit; "
                "otherwise type natural language",
            )
            return False
        if command in {"/jobs", "jobs"}:
            self._render_jobs(output_stream)
            return False
        if command in {"/show", "show"} and argument:
            self._render_detail(argument.strip(), output_stream)
            return False
        if command in {"/events", "events"} and argument:
            self._render_events(argument.strip(), output_stream)
            return False
        return False

    def _handle_request(
        self, request: str, input_stream: TextIO, output_stream: TextIO
    ) -> None:
        try:
            intent = parse_natural_language(request)
            argv = intent_to_argv(intent)
        except ValueError as exc:
            self._write(output_stream, f"ERROR NATURAL_LANGUAGE_INVALID: {exc}")
            return
        self._write(output_stream, f"Intent: {intent.operation.value}")
        self._write(output_stream, f"Canonical CLI: uv run rolo {' '.join(argv)}")
        if not self._requires_confirmation(intent.operation):
            self._execute(intent, output_stream)
            return
        self._write(output_stream, "This operation may write local state or run Adapt.")
        if not self._confirm(input_stream, output_stream):
            self._write(output_stream, "cancelled")
            return
        self._execute(intent, output_stream)

    @staticmethod
    def _requires_confirmation(operation: NaturalLanguageOperation) -> bool:
        return operation not in {
            NaturalLanguageOperation.INSPECT,
            NaturalLanguageOperation.JOB_RECOVER,
        }

    def _confirm(self, input_stream: TextIO, output_stream: TextIO) -> bool:
        if self.confirm is not None:
            return self.confirm("Proceed? [y/N] ")
        self._write(output_stream, "Proceed? [y/N] ", end="")
        answer = input_stream.readline().strip().casefold()
        return answer in {"y", "yes"}

    def _execute(self, intent, output_stream: TextIO) -> None:
        try:
            result = self.service.execute(intent)
        except (OSError, ValueError) as exc:
            self._write(output_stream, f"ERROR EXECUTION_FAILED: {exc}")
            return
        payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        self._write(output_stream, json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    def _render_jobs(self, output_stream: TextIO) -> None:
        state = self.adapter.safe_list_view()
        if state.status == "ERROR":
            assert state.error is not None
            self._write(output_stream, f"ERROR {state.error.code}: {state.error.message}")
            return
        assert state.view is not None
        self._write(output_stream, f"Jobs: {state.view.total}")
        for row in state.view.rows:
            self._write(
                output_stream,
                f"  {row.job_id}  {row.status:<9} {row.operation}  {row.target}",
            )

    def _render_detail(self, job_id: str, output_stream: TextIO) -> None:
        state = self.adapter.safe_detail_view(job_id)
        if state.status == "ERROR":
            assert state.error is not None
            self._write(output_stream, f"ERROR {state.error.code}: {state.error.message}")
            return
        assert state.view is not None
        self._write(
            output_stream,
            json.dumps(state.view.model_dump(mode="json"), ensure_ascii=False, indent=2),
        )

    def _render_events(self, job_id: str, output_stream: TextIO) -> None:
        try:
            page = self.adapter.events(job_id)
        except (OSError, ValueError) as exc:
            self._write(output_stream, f"ERROR JOB_QUERY_FAILED: {exc}")
            return
        if not page.items:
            self._write(output_stream, "  (no events)")
            return
        for event in page.items:
            self._write(
                output_stream,
                f"  [{event.sequence}] {event.status.value:<9} {event.event_type}",
            )

    @staticmethod
    def _write(output_stream: TextIO, value: str, *, end: str = "\n") -> None:
        output_stream.write(value + end)
        output_stream.flush()


def run_console(
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> None:
    jobs = JobService(get_settings().rolo_config_dir / "jobs")
    adapter = JobUiAdapter(ServiceJobQueryAdapter(jobs))
    RoloConsole(
        NaturalLanguageService(jobs),
        adapter,
        input_stream=input_stream,
        output_stream=output_stream,
    ).run()
