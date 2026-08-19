from __future__ import annotations

from typing import Any

SUPPORTED_SCHEMA_KEYS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "enum",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "description",
}
SUPPORTED_TYPES = {"object", "array", "string", "number", "integer", "boolean"}


def validate_schema_definition(schema: dict[str, Any], label: str) -> None:
    """Reject JSON Schema features that the adapter runtime cannot enforce."""
    unknown = sorted(set(schema) - SUPPORTED_SCHEMA_KEYS)
    if unknown:
        raise ValueError(f"{label} uses unsupported schema keywords: {unknown}")
    expected = schema.get("type")
    if expected not in SUPPORTED_TYPES:
        raise ValueError(f"{label} has unsupported or missing type: {expected!r}")
    if "enum" in schema and not isinstance(schema["enum"], list):
        raise ValueError(f"{label} enum must be a list")
    if expected == "object":
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            raise ValueError(f"{label} object schema requires properties")
        if not isinstance(schema.get("additionalProperties"), bool):
            raise ValueError(f"{label} object schema requires boolean additionalProperties")
        required = schema.get("required", [])
        if not isinstance(required, list) or any(name not in properties for name in required):
            raise ValueError(f"{label} required fields must be declared properties")
        for name, child in properties.items():
            if not isinstance(child, dict):
                raise ValueError(f"{label}.{name} must be a schema object")
            validate_schema_definition(child, f"{label}.{name}")
    if expected == "array":
        items = schema.get("items")
        if not isinstance(items, dict):
            raise ValueError(f"{label} array schema requires items")
        validate_schema_definition(items, f"{label}[]")


def validate_schema_value(value: Any, schema: dict[str, Any], label: str) -> None:
    python_types = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    expected = schema["type"]
    if not isinstance(value, python_types[expected]) or (
        expected in {"number", "integer"} and isinstance(value, bool)
    ):
        raise ValueError(f"{label} has wrong type; expected {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{label} is not one of the allowed values")
    if expected in {"number", "integer"}:
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"{label} is below the minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"{label} exceeds the maximum")
    if expected == "string":
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise ValueError(f"{label} is shorter than minLength")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ValueError(f"{label} is longer than maxLength")
    if expected == "object":
        properties = schema["properties"]
        missing = [name for name in schema.get("required", []) if name not in value]
        if missing:
            raise ValueError(f"{label} is missing required fields: {missing}")
        extra = sorted(set(value) - set(properties))
        if extra and schema["additionalProperties"] is False:
            raise ValueError(f"{label} contains unknown fields: {extra}")
        for name, item in value.items():
            if name in properties:
                validate_schema_value(item, properties[name], f"{label}.{name}")
    if expected == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise ValueError(f"{label} has fewer than minItems")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ValueError(f"{label} has more than maxItems")
        for index, item in enumerate(value):
            validate_schema_value(item, schema["items"], f"{label}[{index}]")


def validate_object(value: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    validate_schema_definition(schema, f"{label} schema")
    if schema["type"] != "object":
        raise ValueError(f"{label} schema must describe an object")
    validate_schema_value(value, schema, label)
