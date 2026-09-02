<!-- status: active; authority: normative; owner: docs maintainers; last_reviewed: 2026-08-28 -->

# Agent-native Tool 运行边界（Rolo v2 Probe）

Agent-native Tool 是目标 OS、Middleware、hardware 和 application 的受控只读观测通道，不是 Canonical Operation。
它们不进入 Active Tool Catalog，不参与产品 Contract，也不能生成 `VERIFIED` 或 Adapter
Release。

## 当前实现

- descriptor 与 result：`src/rolo/agent_tools/native_tools.py`；
- 固定 argv、`shell=False`、环境清理、超时、输出上限和脱敏由
  `AgentNativeRunner` 强制执行；
- `NativeToolSession` 通过 nonce、TTL、allowlist 和预算绑定一次 Agent-native 调用集合；
- Rolo CLI 直接把受控 Session 暴露给当前 Agent；若宿主需要进程隔离，可复用
  `NativeToolBroker` 的 loopback JSON-line 边界，但它不是独立产品入口或 MCP 服务；
- 每次调用写入 `artifact://native/<robot>/sessions/<session>/calls/...json`，并追加审计记录；
- `rolo-tool-plan/v1` 必须携带 session nonce；Rolo 拒绝只伪造 session id 的计划；
- Session 的 `native_catalog_sha256` 必须与 Runner 的完整目录一致，防止 descriptor/catalog
  漂移。
- v2 Probe 使用 22 个 family-level descriptor，而不是为每个 OS/Middleware/hardware 命令建立一个
  descriptor；family 内的 `mode` 和参数都来自静态 allowlist，仍由 Runner 编译为固定 argv。
- Agent 先读取 Tool Surface，再通过绑定的 ToolPlan 执行；Probe 不自动运行 native
  工具，也不把 native 结果变成 release authority。
- 对具有外部网络依赖的 Middleware 调用（当前为 `native.middleware.snapshot`），结果在超时时保留
  `TIMEOUT`，同时设置 `environment_limited=true` 并给出明确限制说明。这样可以区分真实
  工具故障和控制器/目标运行环境限制，不能把环境限制伪装成成功。

## 与 Registry 的关系

Probe 不要求 Agent 读取完整 Canonical Registry。Rolo 只发布当前目标的最小 Tool Surface；
当 Native family 无法覆盖某个目标能力时，才进入显式 gap/probe/conformance 流程。

## 接入规则

1. Agent 只能通过受控 Session/ToolPlan 请求 `tool_id`，不能提交任意 argv；
   family Tool 使用 `native run FAMILY_ID --mode MODE [--PARAM VALUE]`，参数由 Broker 和
   Runner 双重校验；
2. Native result 必须携带状态、输出 hash、限制说明和 artifact/evidence ref；
3. Native evidence 只能作为 `OBSERVED`/`UNVERIFIED` 输入，不能替代独立 Gate；
4. v2 Session 不承诺旧 Operation/Registry 兼容；旧 wrapper 不得成为 v2 的隐式执行路径；
5. 新增 family 或 Adapter 前，必须先有目标证据、明确 gap 和独立 conformance。

`sensitive=true` 的 native artifact（例如完整 udev 数据）在 POSIX runner 上以 owner-only
权限落盘；handoff 只携带受校验的引用和 digest，不应把原始内容复制进审计日志。

## Probe provenance chain

Profile 自动装配 pinned SSH connector 后，Tool Surface 输出 session descriptor、surface
digest 和 allowlist；Agent 生成 ToolPlan，Rolo 在 session 内校验 digest、目标、预算和
只读模式，并为每次调用写入 artifact 与审计记录。Adapter bundle 仅在显式能力 gap 时生成。

## Family catalog

当前 v2 family catalog 包含 22 个 MVP provider descriptor。实际 `tool_id` 由目标的
Tool Surface 返回；下面只列出稳定的语义模式，不把任何 OS 或 Middleware 名称写入产品标准。
其他 provider 可复用相同 descriptor 与 conformance 合约：

```text
OS host.inspect / resource.snapshot
OS process.inspect / process.logs
OS service.inspect / service.logs
OS container.inspect / container.logs
OS schedule.inspect / binary.inspect / package.inspect
OS config.inspect / file.inspect / network.snapshot / log.query
Middleware graph.inspect / observe / transform.inspect / bag.inspect / snapshot
hardware inventory / status
```

`logs`、`observe`、`tf` monitor 类能力保留独立风险和时间预算；写操作、校准、reset、
actuator、power、firmware 仍然属于 v2 明确禁止的写/物理动作边界。
