"""Provider-specific JSON Schema compatibility for Codex structured outputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from pydantic import BaseModel

_UNSUPPORTED_OBJECT_BOUNDS = frozenset({"minProperties", "maxProperties"})


def _definition_refs(value: Any) -> set[str]:
    if isinstance(value, dict):
        refs = {
            reference.removeprefix("#/$defs/")
            for reference in [value.get("$ref")]
            if isinstance(reference, str) and reference.startswith("#/$defs/")
        }
        return refs | set().union(*(_definition_refs(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_definition_refs(item) for item in value), set())
    return set()


def _prune_unreferenced_definitions(schema: dict[str, Any]) -> None:
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        return
    root = {key: value for key, value in schema.items() if key != "$defs"}
    reachable = _definition_refs(root)
    pending = list(reachable)
    while pending:
        name = pending.pop()
        for reference in _definition_refs(definitions.get(name)) - reachable:
            reachable.add(reference)
            pending.append(reference)
    for name in set(definitions) - reachable:
        definitions.pop(name)


def codex_output_schema(
    model: type[BaseModel],
    *,
    fixed_string_map_keys: Mapping[str, Sequence[str]] | None = None,
    fixed_string_enums: Mapping[str, Sequence[str]] | None = None,
    closed_object_fields: Sequence[str] = (),
) -> dict[str, Any]:
    """Return a compatible copy while retaining canonical validation after generation."""

    schema = deepcopy(model.model_json_schema())
    fixed_maps = {
        name: sorted(set(keys)) for name, keys in (fixed_string_map_keys or {}).items()
    }
    fixed_enums = {
        name: list(dict.fromkeys(values))
        for name, values in (fixed_string_enums or {}).items()
        if values
    }
    closed_fields = set(closed_object_fields)

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key in _UNSUPPORTED_OBJECT_BOUNDS:
                value.pop(key, None)
            properties = value.get("properties")
            if isinstance(properties, dict):
                for name, values in fixed_enums.items():
                    field_schema = properties.get(name)
                    if not isinstance(field_schema, dict):
                        continue
                    title = field_schema.get("title")
                    field_schema.clear()
                    field_schema.update({"type": "string", "enum": values})
                    if title:
                        field_schema["title"] = title
                for name in closed_fields:
                    field_schema = properties.get(name)
                    if not isinstance(field_schema, dict) or field_schema.get("type") != "object":
                        continue
                    title = field_schema.get("title")
                    field_schema.clear()
                    field_schema.update(
                        {
                            "type": "object",
                            "properties": {},
                            "required": [],
                            "additionalProperties": False,
                        }
                    )
                    if title:
                        field_schema["title"] = title
                for name, keys in fixed_maps.items():
                    field_schema = properties.get(name)
                    if not isinstance(field_schema, dict):
                        continue
                    item_schema = field_schema.get("additionalProperties")
                    if not isinstance(item_schema, dict):
                        continue
                    title = field_schema.get("title")
                    field_schema.clear()
                    field_schema.update(
                        {
                            "type": "object",
                            "properties": {key: deepcopy(item_schema) for key in keys},
                            "required": keys,
                            "additionalProperties": False,
                        }
                    )
                    if title:
                        field_schema["title"] = title
                value["required"] = list(properties)
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(schema)
    _prune_unreferenced_definitions(schema)
    return schema
