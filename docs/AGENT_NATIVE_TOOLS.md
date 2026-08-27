# Agent-native Tool 运行边界

Agent-native Tool 是 Linux、ROS 和部分 HW 的受控只读观测通道，不是 Canonical Operation。
它们不进入 Active Tool Catalog，不参与产品 Contract，也不能生成 `VERIFIED` 或 Adapter
Release。

## 当前实现

- descriptor 与 result：`src/rolo/agent_tools/native_tools.py`；
- 固定 argv、`shell=False`、环境清理、超时、输出上限和脱敏由
  `AgentNativeRunner` 强制执行；
- `NativeToolSession` 通过 nonce、TTL、allowlist 和预算绑定一次 Agent-native 调用集合；
- `NativeToolBroker` 以本机 loopback JSON-line 通道连接 Agent workspace 与 Runner；Agent 只
  能提交 `list`/`run(tool_id)` 请求，不能把任意命令传给宿主进程；
- 每次调用写入 `artifact://native/<robot>/sessions/<session>/calls/...json`，并追加审计记录；
- Session 的 `native_catalog_sha256` 必须与 Runner 的完整目录一致，防止 descriptor/catalog
  漂移。

## 与 Registry 的关系

v1 仍包含 294 项，供旧 release 审计和兼容验证。v2 Canonical Registry 只保留 197 项
Canonical Operation；73 项通用 Linux/ROS/HW 观测能力位于 Agent-native 视图，另有 Product
Control 和 Provider 视图。可用以下命令检查：

```powershell
python -m rolo.cli tool registry --registry-version v2
python -m rolo.cli tool contract validate --registry-version v2
python scripts/validate_registry_migration.py
```

## 接入规则

1. Adapt Agent 只能通过受控 Broker/Session 请求 `tool_id`，不能提交任意 argv；
2. Native result 必须携带状态、输出 hash、限制说明和 artifact/evidence ref；
3. Native evidence 只能作为 `OBSERVED`/`UNVERIFIED` 输入，不能替代独立 Gate；
4. v2 Session 不得调用 v1 Legacy Operation，v1 release 继续使用 v1 resolver；
5. 删除旧 Linux/ROS/HW wrapper 前，必须完成 shadow/canary parity 和人工评审。
