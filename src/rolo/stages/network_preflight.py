"""Bounded connectivity preflight for externally hosted Agent executors."""

from __future__ import annotations

import os
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class AgentNetworkPreflight:
    endpoint_host: str
    endpoint_port: int
    via_proxy: bool


def preflight_agent_network(
    url: str,
    *,
    timeout_s: float = 3.0,
    environment: Mapping[str, str] | None = None,
) -> AgentNetworkPreflight:
    """Prove that the configured endpoint or proxy accepts a bounded TCP connection."""

    if timeout_s <= 0 or timeout_s > 30:
        raise ValueError("Agent network preflight timeout must be in (0, 30]")
    target = urlsplit(url)
    if target.scheme not in {"http", "https"} or not target.hostname:
        raise ValueError("Agent network preflight URL must be http(s)")
    source = environment if environment is not None else os.environ
    proxy_value = (
        source.get("HTTPS_PROXY")
        or source.get("https_proxy")
        if target.scheme == "https"
        else source.get("HTTP_PROXY") or source.get("http_proxy")
    )
    selected = urlsplit(proxy_value) if proxy_value else target
    if selected.scheme not in {"http", "https"} or not selected.hostname:
        raise ValueError("Agent proxy URL must be http(s) and include a host")
    port = selected.port or (443 if selected.scheme == "https" else 80)
    try:
        with socket.create_connection((selected.hostname, port), timeout=timeout_s):
            pass
    except OSError as exc:
        route = "proxy" if proxy_value else "endpoint"
        raise ValueError(f"Agent network {route} preflight failed: {type(exc).__name__}") from exc
    return AgentNetworkPreflight(
        endpoint_host=selected.hostname,
        endpoint_port=port,
        via_proxy=bool(proxy_value),
    )
