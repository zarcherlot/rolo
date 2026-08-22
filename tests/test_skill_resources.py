from pathlib import Path

import pytest

from rolo.stages.adapt.skill_resources import resolve_skill_path

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "skill_name",
    ["rolo-adapt-discovery", "rolo-operation-mapping", "rolo-wiki-authoring"],
)
def test_checkout_skill_override_remains_supported(skill_name: str) -> None:
    expected = ROOT / "skills" / skill_name / "SKILL.md"
    assert resolve_skill_path(expected, skill_name) == expected.resolve()


def test_missing_explicit_skill_override_does_not_silently_fallback(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="configured skill path"):
        resolve_skill_path(tmp_path / "missing.md", "rolo-adapt-discovery")


def test_wheel_configuration_force_includes_all_agent_skill_resources() -> None:
    configuration = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for skill_name in (
        "rolo-adapt-discovery",
        "rolo-operation-mapping",
        "rolo-wiki-authoring",
    ):
        assert f'"skills/{skill_name}" = "rolo/bundled_skills/{skill_name}"' in configuration
