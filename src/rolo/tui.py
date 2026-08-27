"""Minimal dependency-free terminal UI for read-only Job and natural-language queries."""

from __future__ import annotations

import json
import sys
from typing import TextIO

from rolo.natural_language import intent_to_argv, parse_natural_language
from rolo.ui_models import JobUiAdapter


class RoloTui:
    """Line-oriented TUI backed by the shared read-only UI adapter."""

    def __init__(self, adapter: JobUiAdapter) -> None:
        self.adapter = adapter

    def run(
        self,
        *,
        input_stream: TextIO | None = None,
        output_stream: TextIO | None = None,
        once: bool = False,
    ) -> None:
        input_stream = input_stream or sys.stdin
        output_stream = output_stream or sys.stdout
        self._write(output_stream, "Rolo TUI — read-only Job and natural-language console")
        self._write(
            output_stream,
            "Commands: list, show JOB_ID, events JOB_ID, ask TEXT, help, quit",
        )
        self._list(output_stream)
        if once:
            return
        while True:
            self._write(output_stream, "rolo> ", end="")
            line = input_stream.readline()
            if not line:
                return
            command = line.strip()
            if not command:
                continue
            if command in {"quit", "exit", "q"}:
                self._write(output_stream, "bye")
                return
            self._dispatch(command, output_stream)

    def _dispatch(self, command: str, output_stream: TextIO) -> None:
        name, _, argument = command.partition(" ")
        if name == "list":
            self._list(output_stream)
        elif name == "show" and argument:
            self._show(argument.strip(), output_stream)
        elif name == "events" and argument:
            self._events(argument.strip(), output_stream)
        elif name == "ask" and argument:
            self._ask(argument.strip(), output_stream)
        elif name == "help":
            self._write(
                output_stream,
                "list | show JOB_ID | events JOB_ID | ask <自然语言> | help | quit",
            )
        else:
            self._write(output_stream, "invalid command; use help")

    def _list(self, output_stream: TextIO) -> None:
        state = self.adapter.safe_list_view()
        if state.status == "ERROR":
            assert state.error is not None
            self._write(output_stream, f"ERROR {state.error.code}: {state.error.message}")
            return
        assert state.view is not None
        self._write(output_stream, f"Jobs: {state.view.total}")
        if not state.view.rows:
            self._write(output_stream, "  (none)")
            return
        for row in state.view.rows:
            self._write(
                output_stream,
                f"  {row.job_id}  {row.status:<9} {row.operation}  {row.target}",
            )

    def _show(self, job_id: str, output_stream: TextIO) -> None:
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

    def _events(self, job_id: str, output_stream: TextIO) -> None:
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

    def _ask(self, text: str, output_stream: TextIO) -> None:
        try:
            intent = parse_natural_language(text)
            argv = intent_to_argv(intent)
        except ValueError as exc:
            self._write(output_stream, f"ERROR NATURAL_LANGUAGE_INVALID: {exc}")
            return
        self._write(output_stream, f"Intent: {intent.operation.value}")
        self._write(output_stream, f"Canonical CLI: {' '.join(argv)}")
        self._write(
            output_stream,
            "TUI is read-only; use the shown CLI only after normal approval.",
        )

    @staticmethod
    def _write(output_stream: TextIO, value: str, *, end: str = "\n") -> None:
        output_stream.write(value + end)
        output_stream.flush()


def run_tui(
    adapter: JobUiAdapter,
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    once: bool = False,
) -> None:
    RoloTui(adapter).run(input_stream=input_stream, output_stream=output_stream, once=once)
