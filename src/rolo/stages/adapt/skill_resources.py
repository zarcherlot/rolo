from __future__ import annotations

from importlib import resources
from pathlib import Path

_BUNDLED_SKILLS = {
    "rolo-adapt-discovery",
    "rolo-operation-mapping",
    "rolo-wiki-authoring",
}


def resolve_skill_path(configured: Path, skill_name: str) -> Path:
    """Resolve a checkout override first, then the skill shipped in the wheel."""
    requested = configured.expanduser()
    if requested.is_file():
        return requested.resolve()
    if skill_name not in _BUNDLED_SKILLS:
        raise ValueError(f"unknown bundled skill: {skill_name}")
    expected_default = Path("skills") / skill_name / "SKILL.md"
    if requested != expected_default:
        raise FileNotFoundError(f"configured skill path does not exist: {configured}")
    resource = resources.files("rolo").joinpath(
        "bundled_skills", skill_name, "SKILL.md"
    )
    candidate = Path(str(resource))
    if candidate.is_file():
        return candidate.resolve()
    raise FileNotFoundError(
        f"skill not found at configured path {configured} or bundled resource {resource}"
    )
