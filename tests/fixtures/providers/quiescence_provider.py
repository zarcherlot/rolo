"""Test-only bound quiescence provider; never configured by production defaults."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

if sys.argv[1:] != ["lease"]:
    raise SystemExit(2)
request = json.load(sys.stdin)
now = datetime.now(timezone.utc)
json.dump(
    {
        "schema_version": "rolo-execution-quiescence-lease/v1",
        "decision": "ALLOW",
        "lease_id": f"test-lease-{request['request_id']}",
        "request_id": request["request_id"],
        "robot_id": request["robot_id"],
        "operation": request["operation"],
        "input_sha256": request["input_sha256"],
        "scope": "robot_execution",
        "state_revision": "test-state-revision",
        "quiescent_since": (now - timedelta(seconds=5)).isoformat(),
        "expires_at": (
            now + timedelta(seconds=request["requested_lease_s"] + 5)
        ).isoformat(),
    },
    sys.stdout,
)
