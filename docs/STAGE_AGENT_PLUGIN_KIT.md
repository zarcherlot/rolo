# Stage Agent Plugin Kit

Rolo 的 Diagnose/Verify 插件边界由两个 entry-point group 组成：

- `rolo.agent_executors`：返回实现 `execute_stage(task, workspace, on_output)` 的 executor；
- `rolo.harnesses`：返回实现 `run(HarnessRequest, on_output)` 的模型 transport。

插件必须随包提供 `rolo-stage-agent-plugin/v1` manifest。manifest 至少声明 plugin ID、
plugin version、`requires_rolo`、支持的 stages 和两个 entry point，并且
`release_authority` 必须为 `false`。Rolo 在加载代码前可调用
`load_plugin_manifest()` 校验版本兼容性。

参考模板位于 Rolo 工程外的 `rolo-stage-plugin-kit`，包含 Claude Code reference
harness/executor。它只把模型返回的结构化 JSON 交给 Rolo handoff materializer；授权、
输入摘要、输出引用、Diagnose/Verify contract 和 release gate 仍由 Rolo 控制。

插件 conformance 的最低要求：

1. 缺少 `execute_stage` 时 factory 必须被拒绝；
2. executor 只能返回 `artifact://` 输出引用；
3. 输入 hash 或 handoff 校验失败必须使当前 run 失败；
4. 插件不得写入 release authority 或绕过用户确认；
5. 插件 manifest 与当前 Rolo 版本不兼容时不得加载。

模板验证命令：

```powershell
python -c "from pathlib import Path; from rolo.stages.plugin_manifest import load_plugin_manifest; print(load_plugin_manifest(Path('plugin-manifest.json')))"
```
