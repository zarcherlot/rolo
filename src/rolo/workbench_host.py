from __future__ import annotations

import hashlib
import json
import logging
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from rolo.adapt_read_models import ADAPT_API_FEATURES
from rolo.api import app as control_plane_app
from rolo.approval_gate_read_models import APPROVAL_GATE_API_FEATURES
from rolo.artifact_analysis import ARTIFACT_ANALYSIS_API_FEATURES
from rolo.artifact_ingestion import ARTIFACT_INGESTION_API_FEATURES
from rolo.core.config import get_settings
from rolo.episode_read_models import EPISODE_API_FEATURES
from rolo.target_readiness import TARGET_READINESS_API_FEATURES

LOGGER = logging.getLogger(__name__)

MAX_MANIFEST_BYTES = 256 * 1024
MAX_CHECKSUM_BYTES = 1024 * 1024
MAX_PLUGIN_FILES = 2048
MAX_PLUGIN_FILE_BYTES = 16 * 1024 * 1024
MAX_PLUGIN_TOTAL_BYTES = 256 * 1024 * 1024

SUPPORTED_API_FEATURES = frozenset(
    [
        *ADAPT_API_FEATURES,
        *EPISODE_API_FEATURES,
        *TARGET_READINESS_API_FEATURES,
        *APPROVAL_GATE_API_FEATURES,
        *ARTIFACT_ANALYSIS_API_FEATURES,
        *ARTIFACT_INGESTION_API_FEATURES,
    ]
)
SAFE_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64})  ([^\r\n]+)$")
HASHED_ASSET = re.compile(r"-[A-Za-z0-9_-]{6,}\.[A-Za-z0-9]+$")

MIME_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".gif": "image/gif",
    ".html": "text/html; charset=utf-8",
    ".ico": "image/x-icon",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; base-uri 'none'; connect-src 'self'; "
        "font-src 'self'; frame-ancestors 'none'; img-src 'self' data:; "
        "object-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


class WorkbenchPluginError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeliveryContract(StrictModel):
    mode: Literal["device-local"]
    mount_path: Literal["/workbench/"]
    spa_fallback: Literal["scoped"]


class ApiContract(StrictModel):
    base_path: Literal["/rolo-api"]
    required_features: list[str] = Field(max_length=128)
    required_endpoints: list[str] = Field(min_length=1, max_length=128)

    @field_validator("required_features", "required_endpoints")
    @classmethod
    def unique_bounded_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("duplicate API contract value")
        if any(not value or len(value) > 256 for value in values):
            raise ValueError("API contract value is empty or too long")
        return values


class SecurityContract(StrictModel):
    mode: Literal["read-only"]
    remote_access: Literal["loopback-or-trusted-reverse-proxy"]
    allows_arbitrary_commands: Literal[False]
    allows_secret_payloads: Literal[False]


class IntegrityContract(StrictModel):
    algorithm: Literal["sha256"]
    manifest: Literal["SHA256SUMS"]


class WorkbenchPluginManifest(StrictModel):
    schema_version: Literal["rolo-plugin/v2"]
    id: str
    name: str = Field(min_length=1, max_length=128)
    version: str
    kind: Literal["web-workbench"]
    entry: Literal["dist/client/index.html"]
    delivery: DeliveryContract
    capabilities: list[str] = Field(max_length=128)
    api: ApiContract
    security: SecurityContract
    integrity: IntegrityContract

    @field_validator("id")
    @classmethod
    def valid_plugin_id(cls, value: str) -> str:
        if SAFE_ID.fullmatch(value) is None:
            raise ValueError("invalid plugin id")
        return value

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        try:
            Version(value)
        except InvalidVersion as exc:
            raise ValueError("invalid plugin version") from exc
        return value

    @field_validator("capabilities")
    @classmethod
    def unique_capabilities(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("duplicate capability")
        if any(not value or len(value) > 128 for value in values):
            raise ValueError("invalid capability")
        return values

    @model_validator(mode="after")
    def require_supported_features(self) -> WorkbenchPluginManifest:
        if not set(self.api.required_features).issubset(SUPPORTED_API_FEATURES):
            raise ValueError("required API feature is unavailable")
        return self


@dataclass(frozen=True)
class ValidatedStaticFile:
    path: Path
    sha256: str


@dataclass(frozen=True)
class ValidatedWorkbenchPlugin:
    root: Path
    manifest: WorkbenchPluginManifest
    browser_files: dict[str, ValidatedStaticFile]


@dataclass(frozen=True)
class WorkbenchDiagnostic:
    status: Literal["DISABLED", "AVAILABLE", "REJECTED"]
    reason_code: str
    plugin_id: str | None = None
    plugin_version: str | None = None


def _reject(reason_code: str) -> None:
    raise WorkbenchPluginError(reason_code)


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _reject("DUPLICATE_MANIFEST_KEY")
        result[key] = value
    return result


def _read_bounded(path: Path, limit: int, reason_code: str) -> bytes:
    try:
        size = path.stat().st_size
        if size <= 0 or size > limit:
            _reject(reason_code)
        return path.read_bytes()
    except WorkbenchPluginError:
        raise
    except OSError:
        _reject(reason_code)


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        _reject("PACKAGE_PATH_UNREADABLE")
    file_attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return path.is_symlink() or bool(file_attributes & reparse_flag)


def _safe_package_path(value: str) -> PurePosixPath:
    if not value or "\\" in value or "\x00" in value:
        _reject("UNSAFE_PACKAGE_PATH")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        _reject("UNSAFE_PACKAGE_PATH")
    if any(part.startswith(".") for part in path.parts) or path.suffix.casefold() == ".map":
        _reject("FORBIDDEN_PACKAGE_FILE")
    return path


def _parse_manifest(path: Path) -> WorkbenchPluginManifest:
    raw = _read_bounded(path, MAX_MANIFEST_BYTES, "INVALID_MANIFEST")
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object)
        return WorkbenchPluginManifest.model_validate(payload)
    except WorkbenchPluginError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        _reject("INVALID_MANIFEST")


def _parse_checksums(path: Path) -> dict[str, str]:
    raw = _read_bounded(path, MAX_CHECKSUM_BYTES, "INVALID_CHECKSUM_MANIFEST")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        _reject("INVALID_CHECKSUM_MANIFEST")
    checksums: dict[str, str] = {}
    casefolded: set[str] = set()
    for line in lines:
        match = CHECKSUM_LINE.fullmatch(line)
        if match is None:
            _reject("INVALID_CHECKSUM_MANIFEST")
        digest, raw_path = match.groups()
        relative = _safe_package_path(raw_path).as_posix()
        folded = relative.casefold()
        if relative in checksums or folded in casefolded:
            _reject("DUPLICATE_CHECKSUM_ENTRY")
        checksums[relative] = digest
        casefolded.add(folded)
    if not checksums:
        _reject("INVALID_CHECKSUM_MANIFEST")
    return checksums


def load_workbench_plugin(plugin_dir: Path) -> ValidatedWorkbenchPlugin:
    configured = plugin_dir.expanduser()
    if _is_link_or_reparse(configured):
        _reject("UNSAFE_PLUGIN_ROOT")
    try:
        root = configured.resolve(strict=True)
    except OSError:
        _reject("PLUGIN_ROOT_UNAVAILABLE")
    if not root.is_dir():
        _reject("PLUGIN_ROOT_UNAVAILABLE")

    manifest = _parse_manifest(root / "rolo.plugin.json")
    checksums = _parse_checksums(root / manifest.integrity.manifest)

    package_files: dict[str, Path] = {}
    casefolded: set[str] = set()
    total_bytes = 0
    try:
        candidates = sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold())
    except OSError:
        _reject("PACKAGE_PATH_UNREADABLE")
    for candidate in candidates:
        if _is_link_or_reparse(candidate):
            _reject("PACKAGE_LINK_REJECTED")
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            _reject("PACKAGE_FILE_TYPE_REJECTED")
        relative = candidate.relative_to(root).as_posix()
        _safe_package_path(relative)
        if relative not in {"rolo.plugin.json", "SHA256SUMS"} and not relative.startswith(
            "dist/client/"
        ):
            _reject("UNEXPECTED_PACKAGE_FILE")
        folded = relative.casefold()
        if folded in casefolded:
            _reject("CASE_COLLIDING_PACKAGE_PATH")
        casefolded.add(folded)
        size = candidate.stat().st_size
        if size > MAX_PLUGIN_FILE_BYTES:
            _reject("PACKAGE_FILE_TOO_LARGE")
        total_bytes += size
        if total_bytes > MAX_PLUGIN_TOTAL_BYTES:
            _reject("PACKAGE_TOO_LARGE")
        package_files[relative] = candidate
        if len(package_files) > MAX_PLUGIN_FILES:
            _reject("TOO_MANY_PACKAGE_FILES")

    expected = set(package_files) - {"SHA256SUMS"}
    if set(checksums) != expected:
        _reject("CHECKSUM_COVERAGE_MISMATCH")
    for relative, digest in checksums.items():
        actual = hashlib.sha256(package_files[relative].read_bytes()).hexdigest()
        if actual != digest:
            _reject("CHECKSUM_MISMATCH")

    if manifest.entry not in package_files:
        _reject("ENTRY_NOT_FOUND")
    browser_files: dict[str, ValidatedStaticFile] = {}
    prefix = "dist/client/"
    for relative, path in package_files.items():
        if not relative.startswith(prefix):
            continue
        browser_path = relative.removeprefix(prefix)
        suffix = Path(browser_path).suffix.casefold()
        if suffix not in MIME_TYPES:
            _reject("UNSUPPORTED_STATIC_MEDIA_TYPE")
        browser_files[browser_path] = ValidatedStaticFile(
            path=path,
            sha256=checksums[relative],
        )
    if "index.html" not in browser_files:
        _reject("ENTRY_NOT_FOUND")

    return ValidatedWorkbenchPlugin(root=root, manifest=manifest, browser_files=browser_files)


class WorkbenchHost:
    def __init__(
        self,
        api_app: ASGIApp,
        plugin: ValidatedWorkbenchPlugin | None,
        diagnostic: WorkbenchDiagnostic,
    ) -> None:
        self.api_app = api_app
        self.plugin = plugin
        self.diagnostic = diagnostic

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.api_app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path == "/rolo-api" or path.startswith("/rolo-api/"):
            normalized = path.removeprefix("/rolo-api") or "/"
            api_scope = dict(scope)
            api_scope["path"] = normalized
            api_scope["raw_path"] = normalized.encode("utf-8")
            await self.api_app(api_scope, receive, send)
            return
        if path == "/workbench" or path.startswith("/workbench/"):
            await self._serve_workbench(scope, receive, send)
            return
        await self.api_app(scope, receive, send)

    async def _serve_workbench(self, scope: Scope, receive: Receive, send: Send) -> None:
        method = scope.get("method", "GET").upper()
        if method not in {"GET", "HEAD"}:
            await Response(status_code=405, headers={"Allow": "GET, HEAD"})(scope, receive, send)
            return
        if self.plugin is None:
            await JSONResponse(
                {"detail": "Workbench plugin unavailable", "reason": self.diagnostic.reason_code},
                status_code=404,
                headers=SECURITY_HEADERS,
            )(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/workbench":
            query = scope.get("query_string", b"")
            suffix = f"?{query.decode('ascii')}" if query else ""
            await RedirectResponse(f"/workbench/{suffix}", status_code=307)(scope, receive, send)
            return

        relative = path.removeprefix("/workbench/")
        try:
            _safe_package_path(relative) if relative else None
        except WorkbenchPluginError:
            await Response(status_code=404, headers=SECURITY_HEADERS)(scope, receive, send)
            return

        selected = relative or "index.html"
        static_file = self.plugin.browser_files.get(selected)
        if static_file is None:
            if selected.startswith("assets/") or PurePosixPath(selected).suffix:
                await Response(status_code=404, headers=SECURITY_HEADERS)(scope, receive, send)
                return
            selected = "index.html"
            static_file = self.plugin.browser_files[selected]

        try:
            content = static_file.path.read_bytes()
        except OSError:
            content = b""
        if hashlib.sha256(content).hexdigest() != static_file.sha256:
            await JSONResponse(
                {"detail": "Workbench plugin unavailable", "reason": "PACKAGE_CHANGED"},
                status_code=503,
                headers=SECURITY_HEADERS,
            )(scope, receive, send)
            return

        cache_control = "no-store" if selected == "index.html" else "no-cache"
        if selected.startswith("assets/") and HASHED_ASSET.search(selected):
            cache_control = "public, max-age=31536000, immutable"
        headers = {
            **SECURITY_HEADERS,
            "Cache-Control": cache_control,
            "Content-Length": str(len(content)),
        }
        response = Response(
            content=content if method == "GET" else b"",
            media_type=MIME_TYPES[static_file.path.suffix.casefold()],
            headers=headers,
        )
        await response(scope, receive, send)


def create_workbench_app(
    plugin_dir: Path | None = None,
    api_app: ASGIApp = control_plane_app,
) -> WorkbenchHost:
    if plugin_dir is None:
        return WorkbenchHost(
            api_app,
            None,
            WorkbenchDiagnostic(status="DISABLED", reason_code="PLUGIN_NOT_CONFIGURED"),
        )
    try:
        plugin = load_workbench_plugin(plugin_dir)
    except WorkbenchPluginError as exc:
        LOGGER.warning("Workbench plugin unavailable: %s", exc.reason_code)
        return WorkbenchHost(
            api_app,
            None,
            WorkbenchDiagnostic(status="REJECTED", reason_code=exc.reason_code),
        )
    return WorkbenchHost(
        api_app,
        plugin,
        WorkbenchDiagnostic(
            status="AVAILABLE",
            reason_code="VALIDATED",
            plugin_id=plugin.manifest.id,
            plugin_version=plugin.manifest.version,
        ),
    )


app = create_workbench_app(get_settings().rolo_workbench_plugin_dir)
