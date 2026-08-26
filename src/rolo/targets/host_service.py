from __future__ import annotations

import hashlib
import json
import shlex
from base64 import b64encode
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_SHA256 = r"^[0-9a-f]{64}$"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


class TargetHostServiceOperation(str, Enum):
    START = "START"
    STATUS = "STATUS"


class TargetHostServiceStatus(str, Enum):
    STARTED = "STARTED"
    ALREADY_ACTIVE = "ALREADY_ACTIVE"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    FAILED = "FAILED"


class TargetHostServiceError(str, Enum):
    CANCELLED = "CANCELLED"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    CREDENTIAL_UNAVAILABLE = "CREDENTIAL_UNAVAILABLE"
    HOST_PLAN_MISMATCH = "HOST_PLAN_MISMATCH"
    INVALID_REQUEST = "INVALID_REQUEST"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    RUNTIME_MISMATCH = "RUNTIME_MISMATCH"
    SUDO_UNAVAILABLE = "SUDO_UNAVAILABLE"
    SYSTEMD_FAILED = "SYSTEMD_FAILED"


class TargetHostServiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-service-request/v1"] = (
        "rolo-target-host-service-request/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER)
    operation: TargetHostServiceOperation
    target_id: str = Field(pattern=_IDENTIFIER)
    expected_host_plan_sha256: str = Field(pattern=_SHA256)
    expected_runtime_manifest_sha256: str = Field(pattern=_SHA256)
    unit_name: str = Field(
        pattern=r"^rolo-bootstrap-agentd@[A-Za-z0-9._-]+\.service$"
    )

    @model_validator(mode="after")
    def bind_unit(self) -> TargetHostServiceRequest:
        if self.unit_name != f"rolo-bootstrap-agentd@{self.target_id}.service":
            raise ValueError("target host service unit differs from target")
        return self

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.model_dump(mode="json"))


class TargetHostServiceExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-service-execution-result/v1"] = (
        "rolo-target-host-service-execution-result/v1"
    )
    request_id: str = Field(pattern=_IDENTIFIER)
    request_sha256: str = Field(pattern=_SHA256)
    target_id: str = Field(pattern=_IDENTIFIER)
    operation: TargetHostServiceOperation
    executor_kind: Literal["SSH"] = "SSH"
    status: TargetHostServiceStatus
    active: bool | None = None
    error_code: TargetHostServiceError | None = None
    observed_host_plan_sha256: str | None = Field(default=None, pattern=_SHA256)
    observed_runtime_manifest_sha256: str | None = Field(default=None, pattern=_SHA256)
    started_at: datetime
    finished_at: datetime

    @model_validator(mode="after")
    def bind_result(self) -> TargetHostServiceExecutionResult:
        if self.started_at.tzinfo is None or self.finished_at.tzinfo is None:
            raise ValueError("target host service timestamps must be timezone-aware")
        if self.finished_at < self.started_at:
            raise ValueError("target host service finish precedes start")
        if self.status == TargetHostServiceStatus.FAILED:
            if self.error_code is None or self.active is not None:
                raise ValueError("failed host service result is inconsistent")
        else:
            if self.error_code is not None or self.active is None:
                raise ValueError("successful host service result is inconsistent")
            if self.status in {
                TargetHostServiceStatus.STARTED,
                TargetHostServiceStatus.ALREADY_ACTIVE,
                TargetHostServiceStatus.ACTIVE,
            } and not self.active:
                raise ValueError("active host service status requires active=true")
            if self.status == TargetHostServiceStatus.INACTIVE and self.active:
                raise ValueError("inactive host service status requires active=false")
            if (
                self.observed_host_plan_sha256 is None
                or self.observed_runtime_manifest_sha256 is None
            ):
                raise ValueError("successful host service result requires observed digests")
        if self.operation == TargetHostServiceOperation.START and self.status in {
            TargetHostServiceStatus.ACTIVE,
            TargetHostServiceStatus.INACTIVE,
        }:
            raise ValueError("start operation returned a status-only outcome")
        if self.operation == TargetHostServiceOperation.STATUS and self.status in {
            TargetHostServiceStatus.STARTED,
            TargetHostServiceStatus.ALREADY_ACTIVE,
        }:
            raise ValueError("status operation returned a mutation outcome")
        return self


_HOST_SERVICE_SCRIPT = r'''import json,os,re,stat,subprocess,sys
from datetime import datetime,timezone

DIGEST=re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
started=datetime.now(timezone.utc)
request=None
request_sha="0"*64
host_plan=None
runtime_manifest=None
def canonical(value):
 import hashlib
 raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
 return raw,hashlib.sha256(raw).hexdigest()
def emit(status,active=None,error=None):
 payload={"schema_version":"rolo-target-host-service-execution-result/v1",
  "request_id":request.get("request_id","invalid") if isinstance(request,dict) else "invalid",
  "request_sha256":request_sha,
  "target_id":request.get("target_id","invalid") if isinstance(request,dict) else "invalid",
  "operation":request.get("operation","STATUS") if isinstance(request,dict) else "STATUS",
  "executor_kind":"SSH","status":status,"active":active,"error_code":error,
  "observed_host_plan_sha256":host_plan,"observed_runtime_manifest_sha256":runtime_manifest,
  "started_at":started.isoformat(),"finished_at":datetime.now(timezone.utc).isoformat()}
 print(json.dumps(payload,sort_keys=True,separators=(",",":")))
def read_json(path,limit):
 info=os.lstat(path)
 if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_size>limit:
  raise ValueError("unsafe state")
 with open(path,"r",encoding="utf-8") as stream: return json.load(stream)
raw=sys.stdin.buffer.read(65537)
try:
 if len(raw)>65536 or os.geteuid()!=0: raise PermissionError("root")
 request=json.loads(raw.decode("utf-8"));_,request_sha=canonical(request)
 expected={"schema_version","request_id","operation","target_id","expected_host_plan_sha256",
  "expected_runtime_manifest_sha256","unit_name"}
 if not isinstance(request,dict) or set(request)!=expected: raise ValueError("shape")
 target=request["target_id"];operation=request["operation"]
 if (request["schema_version"]!="rolo-target-host-service-request/v1"
     or operation not in ("START","STATUS") or not IDENTIFIER.fullmatch(target or "")):
  raise ValueError("request")
 if (not DIGEST.fullmatch(request["expected_host_plan_sha256"] or "")
     or not DIGEST.fullmatch(request["expected_runtime_manifest_sha256"] or "")):
  raise ValueError("digest")
 unit=f"rolo-bootstrap-agentd@{target}.service"
 if request["unit_name"]!=unit: raise ValueError("unit")
 host_state=read_json("/var/lib/rolo/host-provisioning.json",65536)
 host_plan=host_state.get("plan_sha256")
 if (host_state.get("schema_version")!="rolo-target-host-provisioning-state/v1"
     or host_state.get("target_id")!=target or host_plan!=request["expected_host_plan_sha256"]):
  emit("FAILED",error="HOST_PLAN_MISMATCH");raise SystemExit(0)
 runtime_state=read_json("/var/lib/rolo/.local/share/rolo/runtime/current.json",65536)
 current=runtime_state.get("current") if isinstance(runtime_state,dict) else None
 runtime_manifest=current.get("manifest_sha256") if isinstance(current,dict) else None
 if (runtime_state.get("schema_version")!="rolo-target-install-index/v1"
     or runtime_manifest!=request["expected_runtime_manifest_sha256"]):
  emit("FAILED",error="RUNTIME_MISMATCH");raise SystemExit(0)
 active=(subprocess.run(["systemctl","is-active","--quiet",unit],stdin=subprocess.DEVNULL,
  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30).returncode==0)
 if operation=="STATUS":
  emit("ACTIVE" if active else "INACTIVE",active=active);raise SystemExit(0)
 if active:
  emit("ALREADY_ACTIVE",active=True);raise SystemExit(0)
 subprocess.run(["systemctl","start",unit],stdin=subprocess.DEVNULL,
  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=30)
 active=(subprocess.run(["systemctl","is-active","--quiet",unit],stdin=subprocess.DEVNULL,
  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30).returncode==0)
 if not active: emit("FAILED",error="SYSTEMD_FAILED")
 else: emit("STARTED",active=True)
except SystemExit: raise
except PermissionError: emit("FAILED",error="SUDO_UNAVAILABLE")
except subprocess.TimeoutExpired: emit("FAILED",error="SYSTEMD_FAILED")
except subprocess.CalledProcessError: emit("FAILED",error="SYSTEMD_FAILED")
except (KeyError,OSError,TypeError,UnicodeError,ValueError): emit("FAILED",error="INVALID_REQUEST")
'''


def host_service_remote_command() -> str:
    encoded = b64encode(_HOST_SERVICE_SCRIPT.encode()).decode("ascii")
    loader = f'import base64;exec(base64.b64decode("{encoded}"))'
    return f"sudo -n python3 -c {shlex.quote(loader)}"
