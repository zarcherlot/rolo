from __future__ import annotations

from pathlib import Path

from rolo.harness import HarnessRequest


def test_example_harness_template_streams_without_authority(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).parents[1] / "examples" / "harness-plugin"))
    try:
        from rolo_example_harness import ExampleHarness
    finally:
        sys.path.pop(0)

    output: list[tuple[str, str]] = []
    harness = ExampleHarness(settings=type("Settings", (), {"coding_agent_model": "fake"})())
    stdout, stderr, code = harness.run(
        HarnessRequest(prompt="hello", workspace=tmp_path),
        on_output=lambda stream, line: output.append((stream, line)),
    )

    assert code == 0
    assert stderr == ""
    assert stdout.startswith("example harness received")
    assert output == [("stdout", stdout)]
    assert not (tmp_path / "AGENTS.md").exists()
