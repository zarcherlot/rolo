# Authored Operation Contracts

This document is generated from `src/rolo/operation_contracts/*.yaml`. 
`RELEASED` contracts back built-in operations; `GATEABLE` contracts may be 
implemented and promoted by Adapt. The remaining product vocabulary stays `DRAFT` 
and cannot become `VERIFIED` until an authored contract is added.

Catalog SHA-256: `8502c722426582fc2e522b5aa3926faf6997272f76da7b9d9af9b1ecdd5b42ad`

| Operation | Lifecycle | Version | Contract SHA-256 |
|---|---|---|---|
| `app.camera.snapshot` | GATEABLE | `1.0.0` | `1429afbe60c0f3505aa0a694d23b6299f2f336944bb651f538ce93714ff16354` |
| `app.localization.status` | GATEABLE | `1.0.0` | `12972f523c601fbf26a872c22cd399aee0b1f0e58f30ccd71b4482ea706602ec` |
| `app.map.inspect` | GATEABLE | `1.0.0` | `503cdf42d94879743c19a9b6cbd3fbd2c9a3a47690bbc2b9feb797b2fdf9113d` |
| `app.robot.discover` | RELEASED | `1.0.0` | `d085a1dbdb9751b8e5524c5fae1de682e011165fa48ac714b518980ab4dac09f` |
| `app.safety.emergency_stop` | GATEABLE | `1.0.0` | `9fa9a76755be0f067308669817a6b0e7b422242f427ab22c105f6037d5b5ce76` |
| `app.safety.protective_stop` | GATEABLE | `1.0.0` | `3e36a4bb9881ddb37c90b4839962e7a255d04c6d12d0c5b2fe4f44b6744b0e01` |
| `app.safety.stop.clear` | GATEABLE | `1.0.0` | `c01770210e5bb308e3d54265e7fc08710ba4a6389a47c99cb644097f78f8f412` |
| `app.teleop.velocity` | GATEABLE | `1.0.0` | `54819262eec0de1c33a983549987ff11d34a13f1664e3e58f4cba6b77ee7c080` |
| `hw.inventory.scan` | RELEASED | `1.0.0` | `2233f66989acd3695467681372228eb4c8aec8398a53a7774f8feecc76dc17c0` |
| `linux.binary.describe` | RELEASED | `1.0.0` | `053afce1960939a04ceef13dd7714b0eace8c4f1c16e37ad72a9fc627e52933b` |
| `linux.cli.probe` | RELEASED | `1.0.0` | `4a6926276772c0c48a2b17c8d6de475126ce89fe5ccbaec7d0af4a2a1eaaf789` |
| `linux.config.locate` | RELEASED | `1.0.0` | `d4572305a79c191225b7c212610240a156a38380e9966754644b8c21f3d064d2` |
| `linux.container.inspect` | RELEASED | `1.0.0` | `40743a60637c3383aa92f14c828161ee4e599581aca3159fe6419eca7f9f11a4` |
| `linux.container.list` | RELEASED | `1.0.0` | `4c75e485bb12fd3a734c0d08c9faf48082fe2ef13fb4584de554e3c37ff08848` |
| `linux.host.inspect` | RELEASED | `1.0.0` | `51b21b3d4cf70a19b3e3975a0cfa3bcad3447c8e1f23f08e69ccbeeb0abd76e1` |
| `linux.host.inventory` | RELEASED | `1.0.0` | `2b01caa37426df04438a27ba06fd3da7e79efe0e304cb339cc6cc3ab69970091` |
| `linux.network.listeners` | RELEASED | `1.0.0` | `a879d7c0e9ec9f76bec3296f38de3148aa82306ac214a0c2788e726165f896ec` |
| `linux.process.inspect` | RELEASED | `1.0.0` | `52b7db51e4aa026da24abf88dabd4bfd7ce2c78183004b9afac74d4101115f2c` |
| `linux.process.list` | RELEASED | `1.0.0` | `109b505ac01365a0aedda8fa02d202f53fc105b31941bda9e56c84f27b14ab25` |
| `linux.schedule.inspect` | RELEASED | `1.0.0` | `add7225b137429c3ef6ab1d8d41e9b01563dab9f0c88831c4476cfcb49e1118b` |
| `linux.schedule.list` | RELEASED | `1.0.0` | `c8c5aa500f6ef7cf6faa44c8a8999ac3f6864376d74a870724e2007976a22008` |
| `linux.service.inspect` | RELEASED | `1.0.0` | `021e903585f30d749218747db5bdab155be9ac959e4bf79cd74aeb07a16363d0` |
| `linux.service.list` | RELEASED | `1.0.0` | `34f3ee937731d41146d04eaf9d9a6f93ac7f093613f44e878e353ad9d1a9f0a4` |
| `middleware.inspect` | RELEASED | `1.0.0` | `3c5129ea7a0bafa977a692d766933d1e1fb7b5c7df871456cda901aa6d38f8db` |
| `ros.graph.snapshot` | RELEASED | `1.0.0` | `9525409705575939b9e9859f25956db0454fdb8a682150812adddb3942256ec4` |
| `ros.node.status` | RELEASED | `1.0.0` | `84d3d7779f4985d574ef9d94a3be9d6ee6c97461985b7eda10ff9d742c0f0f78` |
| `tool.catalog` | RELEASED | `1.0.0` | `3111270ee2d74e766d246cea683b7e72ddd8ed81aa585ce9d929591e039b9130` |
| `tool.schema` | RELEASED | `1.0.0` | `50a899edb4126292971a9ed4c1a135ce00b818f811de30c1842637f886e4e8c1` |

## `app.camera.snapshot`

Capture or reference one bounded frame from a selected camera stream.

- Lifecycle/version: `GATEABLE` / `1.0.0`
- Layer/access/risk: `app` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `1429afbe60c0f3505aa0a694d23b6299f2f336944bb651f538ce93714ff16354`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "camera": {
      "type": "string"
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "camera": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "timestamp": {
      "type": "string"
    },
    "frame_id": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.localization.status`

Read localization readiness and bounded quality metadata without changing state.

- Lifecycle/version: `GATEABLE` / `1.0.0`
- Layer/access/risk: `app` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `12972f523c601fbf26a872c22cd399aee0b1f0e58f30ccd71b4482ea706602ec`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "localized": {
      "type": "boolean"
    },
    "quality": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "frame_id": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.map.inspect`

Read bounded metadata for the active or selected two-dimensional map.

- Lifecycle/version: `GATEABLE` / `1.0.0`
- Layer/access/risk: `app` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `503cdf42d94879743c19a9b6cbd3fbd2c9a3a47690bbc2b9feb797b2fdf9113d`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "map_id": {
      "type": "string"
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "map_id": {
      "type": "string"
    },
    "frame_id": {
      "type": "string"
    },
    "resolution_m": {
      "type": "number",
      "minimum": 0
    },
    "width": {
      "type": "integer",
      "minimum": 0
    },
    "height": {
      "type": "integer",
      "minimum": 0
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.robot.discover`

Discover bounded application entrypoints and declared interfaces from supplied roots.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `app` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl app robot discover`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `d085a1dbdb9751b8e5524c5fae1de682e011165fa48ac714b518980ab4dac09f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "source_roots": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "layer": {
      "type": "string",
      "enum": [
        "application"
      ]
    },
    "status": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "errors": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "layer",
    "status",
    "data",
    "warnings",
    "errors",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.safety.emergency_stop`

Request the target safety controller to enter its emergency-stop state.

- Lifecycle/version: `GATEABLE` / `1.0.0`
- Layer/access/risk: `app` / `write` / `R3`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `9fa9a76755be0f067308669817a6b0e7b422242f427ab22c105f6037d5b5ce76`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "stop_state": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.safety.protective_stop`

Request the target safety controller to enter a protective-stop state.

- Lifecycle/version: `GATEABLE` / `1.0.0`
- Layer/access/risk: `app` / `write` / `R3`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `3e36a4bb9881ddb37c90b4839962e7a255d04c6d12d0c5b2fe4f44b6744b0e01`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "stop_state": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.safety.stop.clear`

Request clearance of a previously established target safety stop state.

- Lifecycle/version: `GATEABLE` / `1.0.0`
- Layer/access/risk: `app` / `write` / `R3`
- Idempotent/cancelable: `false` / `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `c01770210e5bb308e3d54265e7fc08710ba4a6389a47c99cb644097f78f8f412`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "stop_state": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.teleop.velocity`

Submit a bounded planar base velocity command in base_link coordinates.

- Lifecycle/version: `GATEABLE` / `1.0.0`
- Layer/access/risk: `app` / `write` / `R3`
- Idempotent/cancelable: `false` / `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `54819262eec0de1c33a983549987ff11d34a13f1664e3e58f4cba6b77ee7c080`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "linear_x_mps": {
      "type": "number"
    },
    "angular_z_radps": {
      "type": "number"
    }
  },
  "required": [
    "linear_x_mps",
    "angular_z_radps"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `hw.inventory.scan`

Perform bounded read-only inventory of compute, buses, and attached hardware.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl hw inventory scan`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `2233f66989acd3695467681372228eb4c8aec8398a53a7774f8feecc76dc17c0`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "layer": {
      "type": "string",
      "enum": [
        "hw"
      ]
    },
    "status": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "errors": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "layer",
    "status",
    "data",
    "warnings",
    "errors",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.binary.describe`

Describe one binary statically without invoking its operational interface.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux binary describe {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `053afce1960939a04ceef13dd7714b0eace8c4f1c16e37ad72a9fc627e52933b`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "path"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.cli.probe`

Run bounded self-description arguments against one explicit executable.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux cli probe {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `4a6926276772c0c48a2b17c8d6de475126ce89fe5ccbaec7d0af4a2a1eaaf789`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    },
    "args": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "maxItems": 8
    }
  },
  "required": [
    "path"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.config.locate`

Locate bounded configuration candidates for a process or binary.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux config locate`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `d4572305a79c191225b7c212610240a156a38380e9966754644b8c21f3d064d2`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "process": {
      "type": "integer",
      "minimum": 1
    },
    "binary": {
      "type": "string",
      "minLength": 1
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.container.inspect`

Inspect one local container using an optional explicit runtime selection.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux container inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `40743a60637c3383aa92f14c828161ee4e599581aca3159fe6419eca7f9f11a4`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    },
    "runtime": {
      "type": "string"
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.container.list`

List bounded metadata for local containers without changing their state.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux container list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `4c75e485bb12fd3a734c0d08c9faf48082fe2ef13fb4584de554e3c37ff08848`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "runtime": {
      "type": "string"
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.host.inspect`

Read the host inventory through the compatibility inspection command.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux host inspect`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `51b21b3d4cf70a19b3e3975a0cfa3bcad3447c8e1f23f08e69ccbeeb0abd76e1`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.host.inventory`

Inventory host identity and available local control planes without mutation.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux host inventory`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `2b01caa37426df04438a27ba06fd3da7e79efe0e304cb339cc6cc3ab69970091`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.network.listeners`

List bounded local listening sockets and owning processes when available.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network listeners`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `a879d7c0e9ec9f76bec3296f38de3148aa82306ac214a0c2788e726165f896ec`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.process.inspect`

Inspect one process tree anchor and its bounded execution context.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux process inspect {pid}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `52b7db51e4aa026da24abf88dabd4bfd7ce2c78183004b9afac74d4101115f2c`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "pid": {
      "type": "integer",
      "minimum": 1
    }
  },
  "required": [
    "pid"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.process.list`

List bounded and redacted process metadata from the local host.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux process list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `109b505ac01365a0aedda8fa02d202f53fc105b31941bda9e56c84f27b14ab25`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.schedule.inspect`

Inspect one system timer or scheduled task without running it.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux schedule inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `add7225b137429c3ef6ab1d8d41e9b01563dab9f0c88831c4476cfcb49e1118b`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.schedule.list`

List bounded system timer, cron, or scheduled task metadata.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux schedule list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `c8c5aa500f6ef7cf6faa44c8a8999ac3f6864376d74a870724e2007976a22008`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.service.inspect`

Inspect one service definition, state, dependencies, and launch context.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux service inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `021e903585f30d749218747db5bdab155be9ac959e4bf79cd74aeb07a16363d0`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.service.list`

List bounded service metadata through the native service manager.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux service list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `34f3ee937731d41146d04eaf9d9a6f93ac7f093613f44e878e353ad9d1a9f0a4`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `middleware.inspect`

Identify available middleware control planes from bounded host evidence.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `middleware` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl middleware inspect`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `3c5129ea7a0bafa977a692d766933d1e1fb7b5c7df871456cda901aa6d38f8db`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string",
      "enum": [
        "middleware.inspect"
      ]
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.graph.snapshot`

Capture a bounded read-only snapshot of the currently observable ROS graph.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros graph snapshot`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `9525409705575939b9e9859f25956db0454fdb8a682150812adddb3942256ec4`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "layer": {
      "type": "string",
      "enum": [
        "ros"
      ]
    },
    "status": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "errors": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "layer",
    "status",
    "data",
    "warnings",
    "errors",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.node.status`

Inspect the observed status and interfaces of one existing ROS node.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros node status {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `84d3d7779f4985d574ef9d94a3be9d6ee6c97461985b7eda10ff9d742c0f0f78`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string",
      "enum": [
        "ros.node.status"
      ]
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `tool.catalog`

Read the active gated Tool Catalog for one robot identity.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `control` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `5s`
- Canonical CLI template: `robotctl tool catalog --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `3111270ee2d74e766d246cea683b7e72ddd8ed81aa585ce9d929591e039b9130`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "robot_id": {
      "type": "string"
    },
    "discovery_id": {
      "type": "string"
    },
    "tools": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "schema_version",
    "robot_id",
    "discovery_id",
    "tools"
  ],
  "additionalProperties": false
}
```

## `tool.schema`

Read the active input and output contract for one canonical operation.

- Lifecycle/version: `RELEASED` / `1.0.0`
- Layer/access/risk: `control` / `read` / `R0`
- Idempotent/cancelable: `true` / `false`
- Maximum duration: `5s`
- Canonical CLI template: `robotctl tool schema {operation} --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `50a899edb4126292971a9ed4c1a135ce00b818f811de30c1842637f886e4e8c1`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "operation": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "operation"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "operation": {
      "type": "string"
    },
    "input_schema": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "output_schema": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "availability": {
      "type": "string"
    }
  },
  "required": [
    "operation",
    "input_schema",
    "output_schema",
    "availability"
  ],
  "additionalProperties": false
}
```
