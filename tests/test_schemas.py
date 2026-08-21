import json
from pathlib import Path

from typer.testing import CliRunner

from rolo.cli import app
from rolo.runtime_context import AdapterRuntimeContext
from rolo.stages.adapt.models import ToolCatalog
from rolo.stages.adapt.operation_registry import (
    CanonicalOperationDefinition,
    canonical_operation_registry,
)


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


def test_exported_tool_catalog_schema_covers_the_complete_artifact() -> None:
    schema = ToolCatalog.model_json_schema()

    assert schema["properties"]["schema_version"]["const"] == "robot-tool-catalog/v1"
    assert set(schema["required"]) == {
        "robot_id",
        "discovery_id",
        "contract_catalog_sha256",
        "tools",
    }
    assert schema["properties"]["tools"]["items"]["$ref"].endswith("/ToolDescriptor")


def test_runtime_context_schema_is_explicit_and_secret_closed() -> None:
    schema = AdapterRuntimeContext.model_json_schema()

    assert schema["additionalProperties"] is False
    assert "ROS_DOMAIN_ID" in schema["properties"]
    assert "AMENT_PREFIX_PATH" in schema["properties"]
    assert "OPENAI_API_KEY" not in schema["properties"]


def test_canonical_operation_definition_has_no_implicit_contract_fields() -> None:
    schema = CanonicalOperationDefinition.model_json_schema()

    assert set(schema["required"]) == set(schema["properties"])


def test_four_layer_operation_document_covers_the_product_registry() -> None:
    documented = {
        line.removeprefix("- `").removesuffix("`")
        for line in Path("docs/CANONICAL_OPERATIONS.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("- `") and line.endswith("`")
    }
    registered = {operation.operation for operation in canonical_operation_registry().operations}

    assert len(registered) == 294
    assert documented == registered
