from __future__ import annotations

import json
import secrets
import socket
import threading
from contextlib import closing

from rolo.agent_tools.session import NativeToolSession

_MAX_REQUEST_BYTES = 16 * 1024
_MAX_RESPONSE_BYTES = 512 * 1024


class NativeToolBroker:
    """Local JSON-line broker that keeps native execution outside the Agent workspace."""

    def __init__(self, session: NativeToolSession) -> None:
        self.session = session
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._token = secrets.token_urlsafe(32)
        self._address: tuple[str, int] | None = None

    @property
    def address(self) -> tuple[str, int]:
        if self._address is None:
            raise RuntimeError("native tool broker is not started")
        return self._address

    @property
    def token(self) -> str:
        return self._token

    def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("native tool broker is already started")
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(8)
        server.settimeout(0.5)
        self._server = server
        host, port = server.getsockname()
        self._address = (str(host), int(port))
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        server = self._server
        self._server = None
        if server is not None:
            server.close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self.session.close()

    def __enter__(self) -> NativeToolBroker:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def _serve(self) -> None:
        server = self._server
        if server is None:
            return
        while not self._stop.is_set():
            try:
                connection, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with closing(connection):
                connection.settimeout(10)
                response = self._handle(self._read_request(connection))
                payload = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
                if len(payload.encode("utf-8")) > _MAX_RESPONSE_BYTES:
                    payload = json.dumps(
                        {"status": "ERROR", "message": "native broker response exceeded limit"}
                    )
                connection.sendall((payload + "\n").encode("utf-8"))

    @staticmethod
    def _read_request(connection: socket.socket) -> dict[str, object] | None:
        chunks = bytearray()
        while len(chunks) <= _MAX_REQUEST_BYTES:
            chunk = connection.recv(4096)
            if not chunk:
                break
            chunks.extend(chunk)
            if b"\n" in chunk:
                break
        if len(chunks) > _MAX_REQUEST_BYTES:
            return None
        try:
            value = json.loads(bytes(chunks).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _handle(self, request: dict[str, object] | None) -> dict[str, object]:
        if request is None or request.get("token") != self._token:
            return {"status": "ERROR", "message": "native broker authorization failed"}
        action = request.get("action")
        try:
            if action == "list":
                return {
                    "status": "SUCCEEDED",
                    "tools": [item.model_dump(mode="json") for item in self.session.list_tools()],
                }
            if action == "run" and isinstance(request.get("tool_id"), str):
                raw_arguments = request.get("arguments", {})
                if not isinstance(raw_arguments, dict) or any(
                    not isinstance(key, str) or not isinstance(value, str)
                    for key, value in raw_arguments.items()
                ):
                    return {"status": "ERROR", "message": "native tool arguments must be strings"}
                return {
                    "status": "SUCCEEDED",
                    "result": self.session.invoke(request["tool_id"], raw_arguments).model_dump(
                        mode="json"
                    ),
                }
            return {"status": "ERROR", "message": "invalid native broker request"}
        except Exception as exc:
            return {"status": "ERROR", "message": str(exc)[:1_000]}


def native_broker_request(
    host: str,
    port: int,
    token: str,
    request: dict[str, object],
    *,
    timeout_s: float = 15,
) -> dict[str, object]:
    payload = dict(request)
    payload["token"] = token
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    if len(encoded) > _MAX_REQUEST_BYTES:
        raise ValueError("native broker request exceeds its byte limit")
    with socket.create_connection((host, port), timeout=timeout_s) as connection:
        connection.sendall(encoded)
        chunks = bytearray()
        while len(chunks) <= _MAX_RESPONSE_BYTES:
            chunk = connection.recv(16 * 1024)
            if not chunk:
                break
            chunks.extend(chunk)
            if b"\n" in chunk:
                break
    if len(chunks) > _MAX_RESPONSE_BYTES:
        raise ValueError("native broker response exceeds its byte limit")
    value = json.loads(bytes(chunks).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("native broker returned an invalid response")
    if value.get("status") == "ERROR":
        raise ValueError(str(value.get("message", "native broker request failed")))
    return value
