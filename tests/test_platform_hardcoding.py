from pathlib import Path

from tools.check_platform_hardcoding import scan


def test_current_core_platform_references_are_explicitly_allowlisted() -> None:
    root = Path(__file__).parents[1] / "src" / "rolo"
    assert scan(root) == []


def test_unallowlisted_platform_reference_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "src" / "rolo"
    source.mkdir(parents=True)
    (source / "bad.py").write_text("def run():\n    return 'nav2_msgs'\n", encoding="utf-8")
    findings = scan(source)
    assert len(findings) == 1
    assert findings[0].token == "nav2_msgs"
