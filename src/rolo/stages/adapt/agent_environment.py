"""Build a bounded, deterministic environment for read-only Codex helpers."""

from __future__ import annotations

import os
from pathlib import Path

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


__all__ = ["codex_helper_environment"]
