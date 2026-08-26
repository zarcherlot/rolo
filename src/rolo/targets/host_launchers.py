from __future__ import annotations

import base64

from rolo.targets.bootstrap_execution import _PREINSTALL_BOOTSTRAP_LAUNCHER_SCRIPT
from rolo.targets.executor import _RUNTIME_CAPABILITIES_SCRIPT
from rolo.targets.package_transfer import _PREINSTALL_TRANSFER_SCRIPT

BOOTSTRAP_DISPATCHER_PATH = "/opt/rolo/libexec/rolo-bootstrap-dispatch"
RUNTIME_LAUNCHER_PATH = "/opt/rolo/bin/robotctl"


def _encoded_script(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def render_bootstrap_dispatcher() -> str:
    """Render the dependency-free forced-command bootstrap dispatcher."""

    capabilities = _encoded_script(_RUNTIME_CAPABILITIES_SCRIPT)
    transfer = _encoded_script(_PREINSTALL_TRANSFER_SCRIPT)
    bootstrap = _encoded_script(_PREINSTALL_BOOTSTRAP_LAUNCHER_SCRIPT)
    return f'''#!/usr/bin/python3
import base64,os,sys

COMMANDS={{
    "robotctl target-executor runtime-capabilities":"{capabilities}",
    "robotctl target-executor package-transfer":"{transfer}",
    "robotctl target-executor bootstrap":"{bootstrap}",
}}
original=os.environ.get("SSH_ORIGINAL_COMMAND","")
encoded=COMMANDS.get(original)
if encoded is None:
    raise SystemExit(2)
source=base64.b64decode(encoded,validate=True).decode("utf-8")
exec(compile(source,"<rolo-bootstrap-dispatch>","exec"),{{"__name__":"__main__"}})
'''


def render_runtime_launcher() -> str:
    """Render the stable launcher that revalidates the active package entrypoint."""

    return r'''#!/usr/bin/python3
import hashlib,json,os,sys

ROOT="/var/lib/rolo/.local/share/rolo/runtime"
INDEX=os.path.join(ROOT,"current.json")
VERSIONS=os.path.realpath(os.path.join(ROOT,"versions"))
DIGEST=set("0123456789abcdef")
def fail():
    raise SystemExit(2)
def digest_file(path):
    digest=hashlib.sha256()
    with open(path,"rb") as stream:
        while True:
            chunk=stream.read(1024*1024)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)
def contained(root,path):
    root=os.path.realpath(root)
    target=os.path.realpath(path)
    if os.path.commonpath((root,target))!=root or os.path.islink(root):
        fail()
    current=root
    relative=os.path.relpath(target,root)
    if relative==".." or relative.startswith("../"):
        fail()
    for part in relative.split(os.sep):
        current=os.path.join(current,part)
        if os.path.islink(current):
            fail()
    return target
try:
    if os.path.getsize(INDEX)>65536:
        fail()
    with open(INDEX,"r",encoding="utf-8") as stream:
        index=json.load(stream)
    expected_index={"schema_version","current","previous","activated_at"}
    if not isinstance(index,dict) or set(index)!=expected_index:
        fail()
    if index["schema_version"]!="rolo-target-install-index/v1":
        fail()
    current=index["current"]
    expected_current={"package_id","package_version","manifest_sha256","install_path"}
    if not isinstance(current,dict) or set(current)!=expected_current:
        fail()
    expected=current["manifest_sha256"]
    if not isinstance(expected,str) or len(expected)!=64 or set(expected)-DIGEST:
        fail()
    install=contained(VERSIONS,current["install_path"])
    if not os.path.isdir(install):
        fail()
    manifest_path=contained(install,os.path.join(install,"target-package.json"))
    if os.path.getsize(manifest_path)>1048576:
        fail()
    with open(manifest_path,"r",encoding="utf-8") as stream:
        manifest=json.load(stream)
    canonical=json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest()!=expected:
        fail()
    identity_matches=(manifest.get("package_id")==current["package_id"]
                      and manifest.get("package_version")==current["package_version"])
    if not identity_matches:
        fail()
    entrypoint=manifest.get("entrypoint")
    if not isinstance(entrypoint,str) or not entrypoint or "\\" in entrypoint or ":" in entrypoint:
        fail()
    parts=entrypoint.split("/")
    if any(not part or part in (".","..") for part in parts):
        fail()
    declarations=[item for item in manifest.get("files",[])
                  if isinstance(item,dict) and item.get("path")==entrypoint
                  and item.get("role")=="ENTRYPOINT"]
    if len(declarations)!=1:
        fail()
    declaration=declarations[0]
    executable=contained(install,os.path.join(install,*parts))
    executable_matches=(os.path.isfile(executable)
                        and os.path.getsize(executable)==declaration.get("size_bytes")
                        and digest_file(executable)==declaration.get("sha256"))
    if not executable_matches:
        fail()
    mode=declaration.get("mode")
    if type(mode) is not int or not 0<=mode<=0o777 or mode&0o111==0:
        fail()
    allowed=("HOME","LANG","LC_ALL","PATH","TMPDIR",
             "ROLO_DEPLOYMENT_AUTHORIZATION_PIN_ROOT")
    safe={name:os.environ[name] for name in allowed if name in os.environ}
    safe.setdefault("HOME","/var/lib/rolo")
    safe.setdefault("PATH","/usr/local/bin:/usr/bin:/bin")
    os.execve(executable,[executable,*sys.argv[1:]],safe)
except SystemExit:
    raise
except (KeyError,OSError,TypeError,UnicodeError,ValueError):
    fail()
'''
