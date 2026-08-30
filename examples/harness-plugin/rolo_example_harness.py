"""Copyable provider-neutral harness plugin skeleton."""

from __future__ import annotations

from rolo.harness import HarnessRequest, ModelHarness, OutputCallback


class ExampleHarness(ModelHarness):
    name = "example"

    def __init__(self, *, settings) -> None:
        self.model = settings.coding_agent_model

    def run(
        self,
        request: HarnessRequest,
        *,
        on_output: OutputCallback | None = None,
    ) -> tuple[str, str, int]:
        del self.model
        line = f"example harness received {len(request.prompt)} characters"
        if on_output is not None:
            on_output("stdout", line)
        return line, "", 0


def factory(*, settings) -> ExampleHarness:
    return ExampleHarness(settings=settings)
