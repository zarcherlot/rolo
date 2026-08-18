import json
from pathlib import Path

from typer.testing import CliRunner

from rolo.cli import app


def test_tracked_schemas_match_canonical_export(tmp_path: Path) -> None:
    output = tmp_path / "schemas"
    result = CliRunner().invoke(app, ["schema", "export", "--output", str(output)])

    assert result.exit_code == 0, result.output
    tracked = {path.name: path for path in Path("schemas").glob("*.schema.json")}
    generated = {path.name: path for path in output.glob("*.schema.json")}
    assert set(tracked) == set(generated)
    for name, path in tracked.items():
        assert json.loads(path.read_text(encoding="utf-8")) == json.loads(
            generated[name].read_text(encoding="utf-8")
        )
