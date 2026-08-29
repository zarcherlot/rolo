from __future__ import annotations

from pathlib import Path


def test_verify_provider_template_declares_stage_and_streams() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).parents[1] / "examples" / "stage-provider"))
    try:
        from rolo_example_verify_provider import ExampleVerifyProvider
    finally:
        sys.path.pop(0)

    provider = ExampleVerifyProvider()
    output: list[tuple[str, str]] = []
    result = provider.execute_stage(
        type("Task", (), {"stage": "verify"})(),
        workspace=Path("."),
        on_output=lambda stream, line: output.append((stream, line)),
    )
    assert provider.stage == "verify"
    assert result == {"status": "staged"}
    assert output == [("stdout", "verify provider staging preflight complete")]
