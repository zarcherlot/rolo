# Web read-model MVP baseline

Status: established baseline

Baseline ID: `rolo-vis-mvp-readonly/2026-08`

This document records the rolo producer side of the first rolo-vis read-only MVP
baseline. The machine-readable contract list is
`schemas/rolo-web-read-model-baseline-v1.json`.

## Frozen producer boundary

The baseline publishes Capability v2 and Discovery v3, including separate advisory
models for Agent inference and target-evidence freshness. Existing v1/v2 consumer
compatibility belongs to rolo-vis; rolo itself continues to produce only the current
versions listed in the manifest.

The baseline does not expose raw heuristic artifacts, collector identity, transport
credentials, arbitrary paths, or request bodies. It does not add any write endpoint.

## Compatibility responsibilities

- rolo owns sanitized states, bounded enums, evidence freshness, and provenance.
- rolo-vis owns accepted historical schema ranges and must not infer missing fields.
- Agent-inferred bindings remain outside ordinary binding readiness.
- `influences_release` remains false for every public heuristic summary.

## Promotion

The manifest and paired rolo-vis `0.19.0` baseline passed backend tests, frontend
baseline verification, and the live `rolo-data` regression. Any successor must
publish an explicit versioned contract rather than mutating these established
semantics in place.
