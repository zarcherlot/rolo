"""Test-only request-bound R3 authorizer; never configured by production defaults."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

if sys.argv[1:] != ["authorize"]:
    raise SystemExit(2)
request = json.load(sys.stdin)
json.dump(
    {
        "schema_version": "rolo-r3-authorization-capability/v1",
        "decision": "ALLOW",
        "authorization_id": f"test-auth-{request['request_id']}",
        "request_id": request["request_id"],
        "robot_id": request["robot_id"],
        "operation": request["operation"],
        "input_sha256": request["input_sha256"],
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(),
    },
    sys.stdout,
)
