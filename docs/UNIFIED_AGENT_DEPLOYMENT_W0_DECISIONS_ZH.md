# 统一 Agent 部署与远程适配 W0 架构决策

状态：`ACCEPTED_FOR_IMPLEMENTATION`

基线：`main@666f35c`

日期：`2026-08-25`

本文冻结 W0 产品与架构边界。后续实现如需偏离，必须新增 ADR，不得通过局部代码静默改变。

## ADR-001：三个正交维度

决策：分别表达 Orchestrator placement、Target transport 和 Interaction surface。

```text
OrchestratorPlacement = TARGET_LOCAL | CONTROLLER
TargetTransport       = LOCAL | SSH
InteractionSurface    = CLI | TUI | GUI | NATURAL_LANGUAGE
```

理由：当前 `EvidenceDeploymentMode.LOCAL/REMOTE` 只描述证据传输，不能决定 Agent、Gate、
release、credential 或 UI 所在位置。

约束：

- LOCAL/SSH Executor 必须实现同一 contract；
- 交互入口只影响 `interaction_surface` 和主体来源，不改变 Gate；
- 不允许从 `remote=true` 推断凭据、信任等级或 release placement。

## ADR-002：一个会话 Agent，多个受控工具

决策：用户只面对一个 Session Agent；对话、计划和部署可以在同一服务进程，但执行权限属于
独立注册的工具能力。

```text
Session Agent
  -> typed command/tool request
  -> policy and approval
  -> credential-aware executor
  -> target
```

Agent 只获得 credential reference，不读取 SSH private key、password、API token 或 Collector
private key。Adapter Agent 不继承 Session Agent 的部署凭据。

自然语言不需要先生成用户可见的完整静态 Plan；所有状态变化必须落到 versioned Command、Job、
Event 和 Approval contract。系统必须能输出等价 canonical CLI。

## ADR-003：SSH 信任与双身份

决策：bootstrap credential 与 runtime credential 分离。

- bootstrap credential 只在安装、升级或恢复任务中按审批使用；
- runtime credential 无 sudo、无 PTY、默认禁用 port/agent/X11 forwarding；
- ordinary Adapt 不重新使用 bootstrap credential；
- credential material 由 Credential Provider 持有，不写入 TargetProfile。

主机信任等级：

| 等级 | 信任根 | 用途 |
|---|---|---|
| `STRICT` | 预置 fingerprint 或 SSH CA | 生产默认 |
| `CONFIRMED` | 用户对带外获得的 fingerprint 明确确认 | 实验室首次接入 |
| `TOFU_DEV` | 首次记录 | 开发，默认关闭 |

host key 变化必须生成新的审批和 transition record。

## ADR-004：Collector v4 使用非对称签名

决策：自主 bootstrap 默认创建 Ed25519 Collector identity。

- private key 在目标生成并保持目标本地；
- descriptor 只返回 public key、key ID、target/collector identity；
- request 继续绑定 robot、nonce、issued/expires 和 requested layers；
- bundle 绑定 payload digest、target time、request identity 并签名；
- rotation 由旧 identity 签署 transition，再固定新 public key；
- v1-v3 HMAC deployment 只读兼容，不自动迁移。

SSH host key 证明连接端点，Collector key 证明可离线复核的证据来源，两者不能互相替代。

## ADR-005：复用 PR #17 Runtime Context 与 Sandbox

决策：统一部署不创建第二套 PATH、PYTHONPATH、virtualenv 或 bubblewrap 规则。

PR #17 已建立的权威包括：

- Bundle Operation scoped CLI `PATH`；
- 受约束 editable root 的显式 `PYTHONPATH`；
- virtualenv interpreter、version-manager alias 和必要 library mount；
- 默认 4 GiB address-space、128 process/thread budget 及配置上限；
- Promotion 只执行 `describe`，不以 `invoke` 探测。

新协议只增加 location、target validation provenance 和 attestation，不降低上述限制。

## ADR-006：Controller + SSH 的目标侧运行位置

决策：Adapter Agent 和独立 Gate 运行在控制器；目标绑定的路径验证、frozen Bundle
`describe` 和授权后的 `invoke` 在目标侧 production sandbox 执行。

```text
controller Adapter Agent
  -> frozen bundle and digest
  -> SSH target staging
  -> target sandbox describe
  -> signed TargetDescribeAttestation
  -> controller independent Gate
  -> immutable controller release + activated target copy
```

控制器不得：

- 对目标绝对 PATH/PYTHONPATH 调用本机 `Path.exists()`；
- 用控制器同路径副本冒充目标文件；
- 将远程 `describe` 替换为本机未绑定执行；
- 在 Promotion、bootstrap 或 smoke 中调用 `invoke`。

TargetDescribeAttestation 必须绑定 robot、collector、target、Bundle、Runtime Context、sandbox
launcher、describe output、freshness 和 release digest。

## ADR-007：目标 companion 采用按需 stdio 协议

决策：Phase B 的 `rolo-target` 是版本化安装的目标 companion，默认通过受限 SSH 按需执行
stdin/stdout 请求，不开放新的网络监听端口。

原因：

- 复用现有 SSH host authentication 和运维边界；
- 降低首版常驻 daemon、mTLS、服务发现和端口策略范围；
- 支持 collector、preflight、release staging、describe 和 activation 的 typed 子命令；
- 后续需要实时 Episode 或 fleet push 时再通过独立 ADR 引入常驻服务。

目标机本地运行完整 Rolo API 是另一种 placement，不要求该 companion 常驻。

## ADR-008：目标端制品格式

决策：MVP 使用签名的 `rolo-target-bundle/v1`，不使用运行时 `git clone + uv sync`。

Bundle 至少包含：

```text
manifest.json
manifest.sig
wheelhouse/
rolo wheel
locked dependency metadata
rolo-target launcher
rolo-adapter-sandbox
SBOM
```

首版要求目标已有受支持的 Python 3.10-3.13；不存在兼容 Python 时 preflight 返回 blocker，
不自主修改系统 Python。自包含 CPython runtime 作为 W3 独立扩展评估。

安装采用 staging -> digest verify -> self-test -> atomic activation。失败保留当前版本。

## ADR-009：Release 权威与副本

决策：控制器保存 Gate 后的权威 immutable release；目标保存按相同 digest 激活的部署副本。

- target current index 只能指向已验证且完整的目标副本；
- controller release index 记录 target deployment digest/status；
- 两边 index 不一致时 Runtime 状态为 `BLOCKED`，不能静默选取任一侧；
- activation/rollback 都产生 DeploymentEvent 和 audit；
- write invocation 继续经过现有 Tool Catalog、Policy、Authorization 和 target fingerprint。

## W0 契约边界

W0 建立以下严格、无秘密模型：

- `TargetProfile`；
- `TargetConnectionProfile`；
- `DeploymentCommand`；
- `DeploymentJob`；
- `DeploymentEvent`；
- `ApprovalRequest`。

W0 不实现 SSH、Job runner、Credential Provider、installer 或 v4 cryptography。它只冻结这些
实现必须遵守的输入、身份和状态边界。
