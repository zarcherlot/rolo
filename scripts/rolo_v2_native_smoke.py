"""Run one bounded Rolo v2 native-tool probe inside a target container.

The script intentionally loads the native runner directly so a target does not need
the full Rolo CLI dependency set just to validate the read-only tool path.
"""

from __future__ import annotations

import importlib.util
import sys


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runtime_context = _load("rolo.runtime_context", "/tmp/rolo/runtime_context.py")
native_tools = _load(
    "rolo.agent_tools.native_tools", "/tmp/rolo/agent_tools/native_tools.py"
)
runner = native_tools.AgentNativeRunner(native_tools.reduced_agent_native_catalog())

for tool_id, arguments in (
    ("native.linux.host.inspect", {"mode": "inventory"}),
    ("native.ros.graph.inspect", {"mode": "nodes"}),
):
    result = runner.run(tool_id, arguments)
    print(result.model_dump_json())
