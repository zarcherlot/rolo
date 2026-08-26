from __future__ import annotations

import hashlib
import json
import re
import shlex
from base64 import b64decode, b64encode
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.targets.bootstrap_templates import (
    TargetHostTemplateBundle,
    render_target_host_templates,
)
from rolo.targets.models import ApprovalAction, TargetConnectionProfile

_SHA256 = r"^[0-9a-f]{64}$"
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_PUBLIC_KEY = r"^ssh-ed25519 [A-Za-z0-9+/]{43}=$"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_ed25519_ssh_public_key(value: str) -> str:
    fields = value.strip().split()
    if len(fields) < 2 or fields[0] != "ssh-ed25519":
        raise ValueError("host provisioning requires an Ed25519 OpenSSH public key")
    canonical = f"ssh-ed25519 {fields[1]}"
    try:
        payload = b64decode(fields[1], validate=True)
    except ValueError as exc:
        raise ValueError("host provisioning SSH public key is invalid base64") from exc
    if len(payload) != 32:
        raise ValueError("host provisioning SSH public key must contain 32 raw bytes")
    return canonical


def ssh_public_key_sha256(value: str) -> str:
    canonical = canonical_ed25519_ssh_public_key(value)
    payload = b64decode(canonical.split()[1], validate=True)
    return hashlib.sha256(payload).hexdigest()


class TargetHostProvisioningOperation(str, Enum):
    ENSURE_GROUP = "ENSURE_GROUP"
    ENSURE_USER = "ENSURE_USER"
    ENSURE_DIRECTORY = "ENSURE_DIRECTORY"
    INSTALL_FILE = "INSTALL_FILE"
    SYSTEMD_DAEMON_RELOAD = "SYSTEMD_DAEMON_RELOAD"
    SYSTEMD_ENABLE = "SYSTEMD_ENABLE"


class TargetHostProvisioningStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(pattern=_IDENTIFIER)
    operation: TargetHostProvisioningOperation
    requires_sudo: Literal[True] = True
    argv: list[str] = Field(default_factory=list, max_length=16)
    effect_path: str | None = Field(default=None, min_length=1, max_length=4096)
    owner: str | None = Field(default=None, pattern=r"^[a-z_][a-z0-9_-]{0,31}$")
    group: str | None = Field(default=None, pattern=r"^[a-z_][a-z0-9_-]{0,31}$")
    mode: int | None = Field(default=None, ge=0, le=0o777)
    content_sha256: str | None = Field(default=None, pattern=_SHA256)
    sanitized_summary: str = Field(min_length=1, max_length=500)


def _provisioning_steps(
    bundle: TargetHostTemplateBundle,
    *,
    authorized_keys_sha256: str,
) -> list[TargetHostProvisioningStep]:
    user = bundle.runtime_user
    unit_path = f"/etc/systemd/system/{bundle.systemd_unit_name}"
    return [
        TargetHostProvisioningStep(
            step_id="ensure-runtime-group",
            operation=TargetHostProvisioningOperation.ENSURE_GROUP,
            argv=["groupadd", "--system", user],
            sanitized_summary=f"Ensure the locked system group {user} exists.",
        ),
        TargetHostProvisioningStep(
            step_id="ensure-runtime-user",
            operation=TargetHostProvisioningOperation.ENSURE_USER,
            argv=[
                "useradd",
                "--system",
                "--gid",
                user,
                "--home-dir",
                "/var/lib/rolo",
                "--create-home",
                "--shell",
                "/usr/sbin/nologin",
                user,
            ],
            sanitized_summary=f"Ensure the locked system account {user} exists.",
        ),
        TargetHostProvisioningStep(
            step_id="ensure-runtime-ssh-directory",
            operation=TargetHostProvisioningOperation.ENSURE_DIRECTORY,
            effect_path="/var/lib/rolo/.ssh",
            owner=user,
            group=user,
            mode=0o700,
            sanitized_summary="Ensure the runtime SSH directory has mode 0700.",
        ),
        TargetHostProvisioningStep(
            step_id="install-bootstrap-dispatcher",
            operation=TargetHostProvisioningOperation.INSTALL_FILE,
            effect_path=bundle.bootstrap_dispatcher_path,
            owner="root",
            group="root",
            mode=0o555,
            content_sha256=bundle.bootstrap_dispatcher_sha256,
            sanitized_summary="Install the digest-bound bootstrap forced-command dispatcher.",
        ),
        TargetHostProvisioningStep(
            step_id="install-runtime-launcher",
            operation=TargetHostProvisioningOperation.INSTALL_FILE,
            effect_path=bundle.runtime_launcher_path,
            owner="root",
            group="root",
            mode=0o555,
            content_sha256=bundle.runtime_launcher_sha256,
            sanitized_summary="Install the launcher that verifies the active runtime manifest.",
        ),
        TargetHostProvisioningStep(
            step_id="install-forced-command-keys",
            operation=TargetHostProvisioningOperation.INSTALL_FILE,
            effect_path="/var/lib/rolo/.ssh/authorized_keys",
            owner=user,
            group=user,
            mode=0o600,
            content_sha256=authorized_keys_sha256,
            sanitized_summary="Install separate bootstrap and runtime forced-command public keys.",
        ),
        TargetHostProvisioningStep(
            step_id="install-systemd-unit",
            operation=TargetHostProvisioningOperation.INSTALL_FILE,
            effect_path=unit_path,
            owner="root",
            group="root",
            mode=0o644,
            content_sha256=bundle.systemd_unit_sha256,
            sanitized_summary=f"Install {bundle.systemd_unit_name} without starting it.",
        ),
        TargetHostProvisioningStep(
            step_id="reload-systemd",
            operation=TargetHostProvisioningOperation.SYSTEMD_DAEMON_RELOAD,
            argv=["systemctl", "daemon-reload"],
            sanitized_summary="Reload systemd after installing the exact unit digest.",
        ),
        TargetHostProvisioningStep(
            step_id="enable-systemd-unit",
            operation=TargetHostProvisioningOperation.SYSTEMD_ENABLE,
            argv=["systemctl", "enable", bundle.systemd_unit_name],
            sanitized_summary="Enable the unit; runtime bootstrap starts it after activation.",
        ),
    ]


class TargetHostProvisioningPlan(BaseModel):
    """Immutable review scope for the first privileged target-host transaction."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-provisioning-plan/v1"] = (
        "rolo-target-host-provisioning-plan/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER)
    target_registration_sha256: str = Field(pattern=_SHA256)
    runtime_user: str = Field(pattern=r"^[a-z_][a-z0-9_-]{0,31}$")
    bootstrap_public_key: str = Field(pattern=_PUBLIC_KEY)
    bootstrap_public_key_sha256: str = Field(pattern=_SHA256)
    runtime_public_key: str = Field(pattern=_PUBLIC_KEY)
    runtime_public_key_sha256: str = Field(pattern=_SHA256)
    authorized_keys: str = Field(min_length=1, max_length=32_768)
    authorized_keys_sha256: str = Field(pattern=_SHA256)
    template_bundle: TargetHostTemplateBundle
    steps: list[TargetHostProvisioningStep] = Field(min_length=1, max_length=32)
    approval_actions: list[Literal[ApprovalAction.USE_SUDO]] = Field(min_length=1)
    expected_current_plan_sha256: str | None = Field(default=None, pattern=_SHA256)

    @field_validator("bootstrap_public_key", "runtime_public_key")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        return canonical_ed25519_ssh_public_key(value)

    @model_validator(mode="after")
    def bind_privileged_effects(self) -> TargetHostProvisioningPlan:
        if self.target_id != self.template_bundle.target_id:
            raise ValueError("host provisioning target identity mismatch")
        if self.runtime_user != self.template_bundle.runtime_user:
            raise ValueError("host provisioning runtime user mismatch")
        if self.bootstrap_public_key_sha256 != ssh_public_key_sha256(
            self.bootstrap_public_key
        ):
            raise ValueError("host provisioning bootstrap public key digest mismatch")
        if self.runtime_public_key_sha256 != ssh_public_key_sha256(
            self.runtime_public_key
        ):
            raise ValueError("host provisioning runtime public key digest mismatch")
        if self.bootstrap_public_key_sha256 == self.runtime_public_key_sha256:
            raise ValueError("host provisioning requires distinct bootstrap and runtime keys")
        expected_keys = (
            f"{self.template_bundle.bootstrap_authorized_keys_options} "
            f"{self.bootstrap_public_key}\n"
            f"{self.template_bundle.authorized_keys_options} {self.runtime_public_key}\n"
        )
        if self.authorized_keys != expected_keys:
            raise ValueError("host provisioning authorized_keys content is not canonical")
        if hashlib.sha256(self.authorized_keys.encode()).hexdigest() != (
            self.authorized_keys_sha256
        ):
            raise ValueError("host provisioning authorized_keys digest mismatch")
        if self.approval_actions != [ApprovalAction.USE_SUDO]:
            raise ValueError("host provisioning requires one USE_SUDO approval")
        if self.steps != _provisioning_steps(
            self.template_bundle,
            authorized_keys_sha256=self.authorized_keys_sha256,
        ):
            raise ValueError("host provisioning steps are not canonical")
        return self

    def canonical_sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()


def build_target_host_provisioning_plan(
    *,
    target_id: str,
    target_registration_sha256: str,
    connection: TargetConnectionProfile,
    bootstrap_public_key: str,
    runtime_public_key: str,
    expected_current_plan_sha256: str | None = None,
) -> TargetHostProvisioningPlan:
    if connection.provisioning_user is None:
        raise ValueError("host provisioning requires an explicit provisioning SSH identity")
    runtime_user = connection.runtime_user
    if runtime_user is None or connection.runtime_credential_ref is None:
        raise ValueError("host provisioning requires an explicit runtime SSH identity")
    if connection.user != runtime_user:
        raise ValueError(
            "host provisioning v1 requires bootstrap and runtime keys on one runtime user"
        )
    bootstrap_key = canonical_ed25519_ssh_public_key(bootstrap_public_key)
    runtime_key = canonical_ed25519_ssh_public_key(runtime_public_key)
    bundle = render_target_host_templates(target_id=target_id, runtime_user=runtime_user)
    authorized_keys = (
        f"{bundle.bootstrap_authorized_keys_options} {bootstrap_key}\n"
        f"{bundle.authorized_keys_options} {runtime_key}\n"
    )
    authorized_keys_sha256 = hashlib.sha256(authorized_keys.encode()).hexdigest()
    return TargetHostProvisioningPlan(
        target_id=target_id,
        target_registration_sha256=target_registration_sha256,
        runtime_user=runtime_user,
        bootstrap_public_key=bootstrap_key,
        bootstrap_public_key_sha256=ssh_public_key_sha256(bootstrap_key),
        runtime_public_key=runtime_key,
        runtime_public_key_sha256=ssh_public_key_sha256(runtime_key),
        authorized_keys=authorized_keys,
        authorized_keys_sha256=authorized_keys_sha256,
        template_bundle=bundle,
        steps=_provisioning_steps(
            bundle,
            authorized_keys_sha256=authorized_keys_sha256,
        ),
        approval_actions=[ApprovalAction.USE_SUDO],
        expected_current_plan_sha256=expected_current_plan_sha256,
    )


class TargetHostProvisioningExecutionStatus(str, Enum):
    APPLIED = "APPLIED"
    ALREADY_CURRENT = "ALREADY_CURRENT"
    FAILED = "FAILED"
    CONFLICT = "CONFLICT"


class TargetHostProvisioningExecutionError(str, Enum):
    CANCELLED = "CANCELLED"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    CREDENTIAL_UNAVAILABLE = "CREDENTIAL_UNAVAILABLE"
    INVALID_PLAN = "INVALID_PLAN"
    IO_ERROR = "IO_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    SUDO_UNAVAILABLE = "SUDO_UNAVAILABLE"
    SYSTEMD_FAILED = "SYSTEMD_FAILED"


class TargetHostProvisioningStepResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(pattern=_IDENTIFIER)
    status: Literal["SUCCEEDED", "ALREADY_CURRENT", "FAILED"]


class TargetHostProvisioningExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-provisioning-execution-result/v1"] = (
        "rolo-target-host-provisioning-execution-result/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER)
    plan_sha256: str = Field(pattern=_SHA256)
    executor_kind: Literal["SSH"] = "SSH"
    status: TargetHostProvisioningExecutionStatus
    error_code: TargetHostProvisioningExecutionError | None = None
    current_plan_sha256: str | None = Field(default=None, pattern=_SHA256)
    steps: list[TargetHostProvisioningStepResult] = Field(default_factory=list, max_length=32)
    started_at: datetime
    finished_at: datetime

    @model_validator(mode="after")
    def bind_outcome(self) -> TargetHostProvisioningExecutionResult:
        if self.finished_at < self.started_at:
            raise ValueError("host provisioning finish time precedes start time")
        if self.status in {
            TargetHostProvisioningExecutionStatus.APPLIED,
            TargetHostProvisioningExecutionStatus.ALREADY_CURRENT,
        }:
            if self.error_code is not None or self.current_plan_sha256 != self.plan_sha256:
                raise ValueError("successful host provisioning result is inconsistent")
        elif self.error_code is None:
            raise ValueError("failed host provisioning result requires an error code")
        return self


class TargetHostProvisioningObservationStatus(str, Enum):
    EXACT = "EXACT"
    NOT_COMMITTED = "NOT_COMMITTED"
    DIFFERENT_CURRENT = "DIFFERENT_CURRENT"
    DRIFTED = "DRIFTED"
    FAILED = "FAILED"


class TargetHostProvisioningObservation(BaseModel):
    """Read-only target observation used to reconcile an unknown apply outcome."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-provisioning-observation/v1"] = (
        "rolo-target-host-provisioning-observation/v1"
    )
    target_id: str = Field(pattern=_IDENTIFIER)
    expected_plan_sha256: str = Field(pattern=_SHA256)
    executor_kind: Literal["SSH"] = "SSH"
    status: TargetHostProvisioningObservationStatus
    current_plan_sha256: str | None = Field(default=None, pattern=_SHA256)
    mismatch_codes: list[str] = Field(default_factory=list, max_length=32)
    error_code: TargetHostProvisioningExecutionError | None = None
    observed_at: datetime

    @field_validator("mismatch_codes")
    @classmethod
    def canonical_mismatches(cls, values: list[str]) -> list[str]:
        if values != sorted(set(values)):
            raise ValueError("host observation mismatch codes must be unique and sorted")
        if any(re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", value) is None for value in values):
            raise ValueError("host observation mismatch code is invalid")
        return values

    @model_validator(mode="after")
    def bind_observation(self) -> TargetHostProvisioningObservation:
        if self.observed_at.tzinfo is None:
            raise ValueError("host observation timestamp must be timezone-aware")
        if self.status == TargetHostProvisioningObservationStatus.EXACT:
            if (
                self.current_plan_sha256 != self.expected_plan_sha256
                or self.mismatch_codes
                or self.error_code is not None
            ):
                raise ValueError("exact host observation is inconsistent")
        elif self.status == TargetHostProvisioningObservationStatus.NOT_COMMITTED:
            if self.current_plan_sha256 is not None or self.error_code is not None:
                raise ValueError("not-committed host observation is inconsistent")
        elif self.status == TargetHostProvisioningObservationStatus.DIFFERENT_CURRENT:
            if (
                self.current_plan_sha256 is None
                or self.current_plan_sha256 == self.expected_plan_sha256
                or self.error_code is not None
            ):
                raise ValueError("different-current host observation is inconsistent")
        elif self.status == TargetHostProvisioningObservationStatus.DRIFTED:
            if not self.mismatch_codes or self.error_code is not None:
                raise ValueError("drifted host observation requires mismatch codes")
        elif self.error_code is None:
            raise ValueError("failed host observation requires an error code")
        return self


_HOST_PROVISIONING_INSTALLER_SCRIPT = r'''import grp,hashlib,json,os,pwd,re,subprocess,sys,tempfile
from datetime import datetime,timezone

DIGEST=re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
EXPECTED_STEPS=[
 "ensure-runtime-group","ensure-runtime-user","ensure-runtime-ssh-directory",
 "install-bootstrap-dispatcher","install-runtime-launcher",
 "install-forced-command-keys","install-systemd-unit","reload-systemd",
 "enable-systemd-unit"]
started=datetime.now(timezone.utc)
completed=[]
plan=None
plan_sha="0"*64
def canonical(value):
 return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def digest(value):
 return hashlib.sha256(value).hexdigest()
def emit(status,error=None,current=None):
 payload={"schema_version":"rolo-target-host-provisioning-execution-result/v1",
  "target_id":plan.get("target_id","invalid") if isinstance(plan,dict) else "invalid",
  "plan_sha256":plan_sha,"executor_kind":"SSH","status":status,
  "error_code":error,"current_plan_sha256":current,"steps":completed,
  "started_at":started.isoformat(),"finished_at":datetime.now(timezone.utc).isoformat()}
 print(json.dumps(payload,sort_keys=True,separators=(",",":")))
def done(step,status="SUCCEEDED"):
 completed.append({"step_id":step,"status":status})
def safe_parent(path):
 current="/"
 for part in path.strip("/").split("/")[:-1]:
  current=os.path.join(current,part)
  if os.path.islink(current):
   raise ValueError("symlink")
def write_file(path,content,mode,uid,gid):
 safe_parent(path)
 parent=os.path.dirname(path)
 os.makedirs(parent,mode=0o755,exist_ok=True)
 fd,temporary=tempfile.mkstemp(prefix=".rolo-host-",dir=parent)
 try:
  with os.fdopen(fd,"wb") as stream:
   stream.write(content);stream.flush();os.fsync(stream.fileno())
  os.chmod(temporary,mode);os.chown(temporary,uid,gid);os.replace(temporary,path)
 finally:
  if os.path.exists(temporary): os.unlink(temporary)
def run(argv):
 subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
  stderr=subprocess.DEVNULL,check=True,timeout=30)
raw=sys.stdin.buffer.read(1000001)
try:
 if len(raw)>1000000 or os.geteuid()!=0: raise PermissionError("root")
 plan=json.loads(raw.decode("utf-8"));plan_sha=digest(canonical(plan))
 valid_schema=(isinstance(plan,dict)
  and plan.get("schema_version")=="rolo-target-host-provisioning-plan/v1")
 if not valid_schema:
  raise ValueError("schema")
 target=plan.get("target_id");user=plan.get("runtime_user");bundle=plan.get("template_bundle")
 valid_identity=(IDENTIFIER.fullmatch(target or "")
  and re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}",user or ""))
 if not valid_identity:
  raise ValueError("identity")
 valid_bundle=(isinstance(bundle,dict)
  and bundle.get("schema_version")=="rolo-target-host-template-bundle/v2")
 if not valid_bundle:
  raise ValueError("bundle")
 if bundle.get("target_id")!=target or bundle.get("runtime_user")!=user: raise ValueError("binding")
 if bundle.get("bootstrap_dispatcher_path")!="/opt/rolo/libexec/rolo-bootstrap-dispatch":
  raise ValueError("dispatcher path")
 if bundle.get("runtime_launcher_path")!="/opt/rolo/bin/robotctl": raise ValueError("launcher path")
 unit_name=f"rolo-bootstrap-agentd@{target}.service"
 if bundle.get("systemd_unit_name")!=unit_name: raise ValueError("unit")
 steps=plan.get("steps")
 if not isinstance(steps,list) or [item.get("step_id") for item in steps]!=EXPECTED_STEPS:
  raise ValueError("steps")
 if any(not isinstance(item,dict) or item.get("requires_sudo") is not True for item in steps):
  raise ValueError("sudo scope")
 contents=[("bootstrap_dispatcher","bootstrap_dispatcher_sha256",256000),
  ("runtime_launcher","runtime_launcher_sha256",128000),
  ("systemd_unit","systemd_unit_sha256",32768)]
 for content_name,digest_name,limit in contents:
  value=bundle.get(content_name);expected=bundle.get(digest_name)
  if not isinstance(value,str) or len(value.encode())>limit or not DIGEST.fullmatch(expected or ""):
   raise ValueError("content")
  if digest(value.encode())!=expected: raise ValueError("content digest")
 keys=plan.get("authorized_keys");keys_digest=plan.get("authorized_keys_sha256")
 if not isinstance(keys,str) or len(keys.encode())>32768 or digest(keys.encode())!=keys_digest:
  raise ValueError("authorized keys")
 expected=plan.get("expected_current_plan_sha256")
 if expected is not None and not DIGEST.fullmatch(expected): raise ValueError("CAS")
 state_path="/var/lib/rolo/host-provisioning.json";current=None
 if os.path.isfile(state_path):
  if os.path.getsize(state_path)>65536: raise ValueError("state")
  with open(state_path,"r",encoding="utf-8") as stream: state=json.load(stream)
  current=state.get("plan_sha256")
  if not DIGEST.fullmatch(current or ""): raise ValueError("state")
 if current==plan_sha:
  for step in EXPECTED_STEPS: done(step,"ALREADY_CURRENT")
  emit("ALREADY_CURRENT",current=plan_sha);raise SystemExit(0)
 if current is not None and expected!=current:
  emit("CONFLICT","INVALID_PLAN",current);raise SystemExit(0)
 if current is None and expected is not None:
  emit("CONFLICT","INVALID_PLAN");raise SystemExit(0)
 try: group=grp.getgrnam(user)
 except KeyError:
  run(["groupadd","--system",user]);group=grp.getgrnam(user)
 done("ensure-runtime-group")
 try: account=pwd.getpwnam(user)
 except KeyError:
  run(["useradd","--system","--gid",user,"--home-dir","/var/lib/rolo",
       "--create-home","--shell","/usr/sbin/nologin",user]);account=pwd.getpwnam(user)
 valid_account=(account.pw_dir=="/var/lib/rolo"
  and account.pw_shell=="/usr/sbin/nologin" and account.pw_gid==group.gr_gid)
 if not valid_account:
  raise ValueError("existing account")
 done("ensure-runtime-user")
 os.makedirs("/var/lib/rolo/.ssh",mode=0o700,exist_ok=True)
 os.chmod("/var/lib/rolo/.ssh",0o700);os.chown("/var/lib/rolo/.ssh",account.pw_uid,group.gr_gid)
 done("ensure-runtime-ssh-directory")
 write_file(bundle["bootstrap_dispatcher_path"],bundle["bootstrap_dispatcher"].encode(),0o555,0,0)
 done("install-bootstrap-dispatcher")
 write_file(bundle["runtime_launcher_path"],bundle["runtime_launcher"].encode(),0o555,0,0)
 done("install-runtime-launcher")
 write_file("/var/lib/rolo/.ssh/authorized_keys",keys.encode(),0o600,account.pw_uid,group.gr_gid)
 done("install-forced-command-keys")
 write_file(f"/etc/systemd/system/{unit_name}",bundle["systemd_unit"].encode(),0o644,0,0)
 done("install-systemd-unit")
 run(["systemctl","daemon-reload"]);done("reload-systemd")
 run(["systemctl","enable",unit_name]);done("enable-systemd-unit")
 state={"schema_version":"rolo-target-host-provisioning-state/v1","target_id":target,
  "plan_sha256":plan_sha,"registration_sha256":plan["target_registration_sha256"],
  "installed_at":datetime.now(timezone.utc).isoformat()}
 write_file(state_path,canonical(state)+b"\n",0o644,0,0)
 emit("APPLIED",current=plan_sha)
except SystemExit: raise
except PermissionError:
 emit("FAILED","SUDO_UNAVAILABLE")
except subprocess.CalledProcessError:
 emit("FAILED","SYSTEMD_FAILED")
except (KeyError,OSError,TypeError,UnicodeError,ValueError):
 emit("FAILED","INVALID_PLAN")
'''


def host_provisioning_remote_command() -> str:
    encoded = b64encode(_HOST_PROVISIONING_INSTALLER_SCRIPT.encode()).decode("ascii")
    loader = f'import base64;exec(base64.b64decode("{encoded}"))'
    return f"sudo -n python3 -c {shlex.quote(loader)}"


_HOST_PROVISIONING_OBSERVER_SCRIPT = r'''import grp,hashlib,json,os,pwd,re,stat,subprocess,sys
from datetime import datetime,timezone

DIGEST=re.compile(r"^[0-9a-f]{64}$")
plan=None
plan_sha="0"*64
def canonical(value):
 return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def digest(value): return hashlib.sha256(value).hexdigest()
def emit(status,current=None,mismatches=None,error=None):
 payload={"schema_version":"rolo-target-host-provisioning-observation/v1",
  "target_id":plan.get("target_id","invalid") if isinstance(plan,dict) else "invalid",
  "expected_plan_sha256":plan_sha,"executor_kind":"SSH","status":status,
  "current_plan_sha256":current,"mismatch_codes":sorted(set(mismatches or [])),
  "error_code":error,"observed_at":datetime.now(timezone.utc).isoformat()}
 print(json.dumps(payload,sort_keys=True,separators=(",",":")))
def file_mismatch(path,content,mode,uid,gid,code):
 try:
  info=os.lstat(path)
  if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode): return code
  if stat.S_IMODE(info.st_mode)!=mode or info.st_uid!=uid or info.st_gid!=gid: return code
  if os.path.getsize(path)>1000000: return code
  with open(path,"rb") as stream: observed=stream.read(1000001)
  if observed!=content: return code
 except (OSError,ValueError): return code
 return None
raw=sys.stdin.buffer.read(1000001)
try:
 if len(raw)>1000000 or os.geteuid()!=0: raise PermissionError("root")
 plan=json.loads(raw.decode("utf-8"));plan_sha=digest(canonical(plan))
 if (not isinstance(plan,dict)
     or plan.get("schema_version")!="rolo-target-host-provisioning-plan/v1"):
  raise ValueError("schema")
 target=plan.get("target_id");user=plan.get("runtime_user");bundle=plan.get("template_bundle")
 if not isinstance(target,str) or not isinstance(user,str) or not isinstance(bundle,dict):
  raise ValueError("shape")
 if bundle.get("target_id")!=target or bundle.get("runtime_user")!=user: raise ValueError("binding")
 if bundle.get("bootstrap_dispatcher_path")!="/opt/rolo/libexec/rolo-bootstrap-dispatch":
  raise ValueError("dispatcher")
 if bundle.get("runtime_launcher_path")!="/opt/rolo/bin/robotctl": raise ValueError("launcher")
 unit=f"rolo-bootstrap-agentd@{target}.service"
 if bundle.get("systemd_unit_name")!=unit: raise ValueError("unit")
 state_path="/var/lib/rolo/host-provisioning.json"
 if not os.path.exists(state_path):
  emit("NOT_COMMITTED",mismatches=["COMMIT_MARKER_ABSENT"]);raise SystemExit(0)
 if (os.path.islink(state_path) or not os.path.isfile(state_path)
     or os.path.getsize(state_path)>65536):
  emit("DRIFTED",mismatches=["COMMIT_MARKER_INVALID"]);raise SystemExit(0)
 with open(state_path,"r",encoding="utf-8") as stream: state=json.load(stream)
 current=state.get("plan_sha256")
 if not DIGEST.fullmatch(current or "") or state.get("target_id")!=target:
  emit("DRIFTED",mismatches=["COMMIT_MARKER_INVALID"]);raise SystemExit(0)
 if current!=plan_sha:
  emit("DIFFERENT_CURRENT",current=current,mismatches=["PLAN_DIGEST_DIFFERS"]);raise SystemExit(0)
 mismatches=[]
 try: group=grp.getgrnam(user);account=pwd.getpwnam(user)
 except KeyError:
  emit("DRIFTED",current=current,mismatches=["RUNTIME_IDENTITY_MISSING"]);raise SystemExit(0)
 if (account.pw_dir!="/var/lib/rolo" or account.pw_shell!="/usr/sbin/nologin"
     or account.pw_gid!=group.gr_gid):
  mismatches.append("RUNTIME_IDENTITY_DRIFT")
 try:
  ssh_info=os.lstat("/var/lib/rolo/.ssh")
  if (not stat.S_ISDIR(ssh_info.st_mode) or stat.S_ISLNK(ssh_info.st_mode)
      or stat.S_IMODE(ssh_info.st_mode)!=0o700
      or ssh_info.st_uid!=account.pw_uid or ssh_info.st_gid!=group.gr_gid):
   mismatches.append("SSH_DIRECTORY_DRIFT")
 except OSError: mismatches.append("SSH_DIRECTORY_DRIFT")
 checks=[
  (bundle["bootstrap_dispatcher_path"],bundle["bootstrap_dispatcher"].encode(),0o555,0,0,"BOOTSTRAP_DISPATCHER_DRIFT"),
  (bundle["runtime_launcher_path"],bundle["runtime_launcher"].encode(),0o555,0,0,"RUNTIME_LAUNCHER_DRIFT"),
  ("/var/lib/rolo/.ssh/authorized_keys",plan["authorized_keys"].encode(),0o600,account.pw_uid,group.gr_gid,"AUTHORIZED_KEYS_DRIFT"),
  (f"/etc/systemd/system/{unit}",bundle["systemd_unit"].encode(),0o644,0,0,"SYSTEMD_UNIT_DRIFT")]
 for args in checks:
  mismatch=file_mismatch(*args)
  if mismatch: mismatches.append(mismatch)
 enabled=subprocess.run(["systemctl","is-enabled","--quiet",unit],stdin=subprocess.DEVNULL,
  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30).returncode
 if enabled!=0: mismatches.append("SYSTEMD_ENABLE_DRIFT")
 if mismatches: emit("DRIFTED",current=current,mismatches=mismatches)
 else: emit("EXACT",current=current)
except SystemExit: raise
except PermissionError: emit("FAILED",error="SUDO_UNAVAILABLE")
except subprocess.TimeoutExpired: emit("FAILED",error="SYSTEMD_FAILED")
except (KeyError,OSError,TypeError,UnicodeError,ValueError): emit("FAILED",error="INVALID_PLAN")
'''


def host_provisioning_observer_remote_command() -> str:
    encoded = b64encode(_HOST_PROVISIONING_OBSERVER_SCRIPT.encode()).decode("ascii")
    loader = f'import base64;exec(base64.b64decode("{encoded}"))'
    return f"sudo -n python3 -c {shlex.quote(loader)}"
