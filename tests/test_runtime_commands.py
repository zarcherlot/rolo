from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from rolo.commands import runtime


def _settings(**kwargs):
    defaults = {
        "rolo_api_token": None,
        "rolo_workbench_plugin_dir": None,
        "rolo_host": "127.0.0.1",
        "rolo_port": 8000,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_runtime_server_application_enforces_binding_policy() -> None:
    assert runtime.runtime_server_application(_settings(), "127.0.0.1") == "rolo.api:app"
    assert runtime.runtime_server_application(_settings(), "localhost") == "rolo.api:app"
    assert (
        runtime.runtime_server_application(
            _settings(rolo_workbench_plugin_dir=Path("plugins")), "127.0.0.1"
        )
        == "rolo.workbench_host:app"
    )
    with pytest.raises(Exception, match="ROLO_API_TOKEN"):
        runtime.runtime_server_application(_settings(), "0.0.0.0")
    with pytest.raises(Exception, match="loopback"):
        runtime.runtime_server_application(
            _settings(rolo_api_token="token", rolo_workbench_plugin_dir=Path("plugins")), "0.0.0.0"
        )


def test_runtime_version_and_health_report(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    runtime.runtime_version()
    assert '"status": "SUCCEEDED"' in capsys.readouterr().out

    class Registry:
        def __len__(self):
            return 2

    monkeypatch.setattr(
        runtime,
        "create_runtime",
        lambda: SimpleNamespace(
            registry=Registry(), artifacts=SimpleNamespace(root=Path("artifacts"))
        ),
    )
    runtime.runtime_health()
    assert '"registered_robots": 2' in capsys.readouterr().out

    monkeypatch.setattr(
        runtime, "create_runtime", lambda: (_ for _ in ()).throw(ValueError("bad config"))
    )
    with pytest.raises(runtime.typer.Exit):
        runtime.runtime_health()
    assert '"status": "UNAVAILABLE"' in capsys.readouterr().out


def test_runtime_serve_passes_resolved_options_to_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        runtime, "get_settings", lambda: _settings(rolo_host="localhost", rolo_port=9000)
    )
    monkeypatch.setattr(runtime, "runtime_server_application", lambda settings, host: "app:obj")
    monkeypatch.setitem(
        __import__("sys").modules,
        "uvicorn",
        SimpleNamespace(
            run=lambda application, **kwargs: calls.update(application=application, **kwargs)
        ),
    )
    runtime.runtime_serve(port=9010, reload=True)
    assert calls == {"application": "app:obj", "host": "localhost", "port": 9010, "reload": True}
