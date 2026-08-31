"""Build a bounded, deterministic environment for read-only Codex helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from rolo.stages.network_preflight import preflight_agent_network

_ALLOWED_KEYS = frozenset(
    {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "TMP",
        "TEMP",
        "HOME",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "APPDATA",
        "LOCALAPPDATA",
        "CODEX_HOME",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
    }
)

DEFAULT_CODEX_API_ENDPOINT = "https://api.openai.com/v1"
DEFAULT_CODEX_CHATGPT_ENDPOINT = "https://chatgpt.com/backend-api/codex"


@dataclass(frozen=True)
class CodexHelperReadiness:
    endpoint_host: str
    endpoint_port: int
    via_proxy: bool
    auth_mode: str


def _value_for(environment: dict[str, str], name: str) -> str | None:
    """Resolve a variable deterministically across Windows, WSL and Linux."""

    lowercase = name.lower()
    if lowercase in environment:
        return environment[lowercase]
    if name in environment:
        return environment[name]
    for key in sorted(environment):
        if key.casefold() == lowercase:
            return environment[key]
    return None


def codex_helper_environment(*, api_key: str | None = None) -> dict[str, str]:
    """Return only safe host settings needed by a read-only Codex helper."""

    source = dict(os.environ)
    result: dict[str, str] = {}
    for name in sorted(_ALLOWED_KEYS):
        value = _value_for(source, name)
        if value is not None:
            result[name] = value
    if "HOME" not in result and result.get("USERPROFILE"):
        result["HOME"] = result["USERPROFILE"]
    if "HOME" not in result and result.get("HOMEDRIVE") and result.get("HOMEPATH"):
        result["HOME"] = result["HOMEDRIVE"] + result["HOMEPATH"]
    if "CODEX_HOME" not in result and result.get("HOME"):
        default_codex_home = Path(result["HOME"]) / ".codex"
        if default_codex_home.is_dir():
            result["CODEX_HOME"] = str(default_codex_home)
    if api_key:
        result["CODEX_API_KEY"] = api_key
    return {key: result[key] for key in sorted(result)}


def preflight_codex_helper(
    *,
    executable: str,
    provider: str,
    base_url: str | None,
    api_key: str | None,
    environment: Mapping[str, str],
    timeout_s: float,
    preflight_url: str | None = None,
) -> CodexHelperReadiness:
    """Verify the exact helper environment can reach its endpoint and has local auth."""

    resolved = shutil.which(executable, path=environment.get("PATH"))
    if resolved is None and not Path(executable).is_file():
        raise ValueError("Codex Agent readiness failed: CLI executable not found")
    is_default_codex = provider.casefold() == "codex" and base_url is None
    endpoint = preflight_url or base_url
    if endpoint is None:
        endpoint = DEFAULT_CODEX_API_ENDPOINT if api_key else DEFAULT_CODEX_CHATGPT_ENDPOINT
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Codex Agent readiness failed: preflight URL must be absolute HTTP(S)")
    try:
        network = preflight_agent_network(
            endpoint,
            timeout_s=timeout_s,
            environment=environment,
        )
    except ValueError as exc:
        raise ValueError(f"Codex Agent readiness failed: {exc}") from exc
    auth_mode = "api_key" if api_key else "provider"
    if is_default_codex and not api_key:
        try:
            completed = subprocess.run(
                [resolved or executable, "login", "status"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=timeout_s,
                env=dict(environment),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(
                f"Codex Agent readiness failed: local login status {type(exc).__name__}"
            ) from exc
        if completed.returncode != 0:
            raise ValueError("Codex Agent readiness failed: Codex CLI is not logged in")
        auth_mode = "chatgpt_login"
    return CodexHelperReadiness(
        endpoint_host=network.endpoint_host,
        endpoint_port=network.endpoint_port,
        via_proxy=network.via_proxy,
        auth_mode=auth_mode,
    )


__all__ = ["CodexHelperReadiness", "codex_helper_environment", "preflight_codex_helper"]
