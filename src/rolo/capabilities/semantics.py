"""External semantic mapping; it does not mutate legacy registry layers."""

from __future__ import annotations

from types import MappingProxyType

from rolo.capabilities.models import SemanticLayer

# ``control`` remains product control-plane metadata rather than a semantic
# platform layer. A ``None`` mapping makes that distinction explicit without
# changing the existing registry value or operation identifiers.
LEGACY_LAYER_SEMANTICS = MappingProxyType(
    {
        "control": None,
        "hw": SemanticLayer.HARDWARE,
        "linux": SemanticLayer.OS,
        "middleware": SemanticLayer.MIDDLEWARE,
        "ros": SemanticLayer.MIDDLEWARE,
        "app": SemanticLayer.APPLICATION,
    }
)


def semantic_layer_for_legacy(layer: str) -> SemanticLayer | None:
    """Return the external semantic layer for a known legacy layer."""

    try:
        return LEGACY_LAYER_SEMANTICS[layer]
    except KeyError as exc:
        raise ValueError(f"unknown legacy operation layer: {layer}") from exc
