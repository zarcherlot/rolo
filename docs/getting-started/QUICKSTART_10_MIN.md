<!-- status: active; authority: guide; owner: rolo maintainers; last_reviewed: 2026-09-02 -->

# Rolo v2：十分钟只读闭环

这条路径的目标只有一个：在自己的机器人上完成 Rolo 初始化，并让当前 Agent 消费一组
经过 Conformance 的只读 Tool。它不会启动、停止、控制或修改机器人。

## 1. 安装与 profile

```bash
uv sync --locked --dev
rolo target profile init ssh://user@target.example/path/to/workspace --robot my-robot
rolo target profile show --profile my-robot
```

首次使用时，用户只批准目标 host key，并完成一次 identity enrollment。密码若被使用，
仅用于这次置备；Rolo 不把密码写入 profile、计划或 artifact。

## 2. 采集目标证据

```bash
rolo target inspect-profile --profile my-robot
rolo probe --profile my-robot --evidence-timeout 60
```

Rolo 自动选择已批准的 connector，在目标自己的 OS/Middleware 环境运行有界 Probe，验证
TargetEvidenceBundle 的目标身份、freshness、digest 和签名。缺少可执行文件、依赖包、
动态库或 Middleware 上下文时，结果会明确失败，不会用控制器环境补齐。

## 3. 让 Agent 使用 Tool

```bash
rolo target tool-surface --profile my-robot > surface.json
# Agent 读取 surface.json 后生成带 session nonce 和 surface digest 的 PLAN.json
rolo target tool-plan --profile my-robot PLAN.json
```

Surface 只包含四类稳定语义中的当前可用只读 family：`hardware`、`OS`、`Middleware`、
`application`。Agent 只能提交 Surface 中的 `tool_id` 和 typed arguments；Rolo 再次校验
目标、session、nonce、digest、allowlist、TTL、预算和只读边界，并为每次调用写 evidence
artifact 与 audit。

## 4. 继续扩展的唯一入口

若 Agent 发现当前 Surface 没有安全、稳定的能力，不提交任意 shell。先形成窄 gap，再由
Rolo 运行 bounded Probe、生成最小 Adapter bundle，并通过独立 Conformance 后才发布这项
新增能力。Trace、Certify、MCP、Web UI 和写/物理动作不属于这条 MVP 闭环。
