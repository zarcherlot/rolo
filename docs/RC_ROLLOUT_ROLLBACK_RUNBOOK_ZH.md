# Rolo Target Runtime RC Rollout / Rollback Runbook

状态：`DRAFT_IN_PROGRESS`。公开的、审批绑定的 target runtime rollback Job、CLI、API、独立 authenticated GUI、
有界交互式 TUI 与 Session Agent broker 已进入软件验证；在真实 x86_64/AArch64 RC 和外部安全评审证据完成前，
不得标记为生产 runbook。

## 1. 适用范围与硬边界

本文只覆盖签名 `rolo-target-package/v1` 的 Target runtime rollout。Adapter release、Collector identity
rotation、机器人运动安全和企业 SSH CA 另走各自 Gate。任何阶段出现未知远端副作用、host-key 变化、签名/SBOM
不一致、Job `BLOCKED/REQUIRES_RECONCILIATION` 或审批过期，都必须停止扩批，不能以重跑命令代替 reconcile。

当前公开控制面支持 package import、Bootstrap submit/approval/run、Job/status/events/cancel，以及 target runtime
rollback submit/approval/run。rollback submission 冻结 target registration、release signing public-key pin、package id、
expected-current/expected-previous digest 和 expiry；Controller 只向 fixed target executor 发送 strict typed request。因此：

- 安装健康检查失败时，由安装事务自动保留旧 current，不需要人工 rollback；
- 激活后才发现回归时，必须停止 rollout，提交独立 R3 rollback Job，并在审批前保持目标不变；
- 不得直接调用 Python 内部类、编辑 `current.json`、替换 symlink 或用 raw SSH 模拟正式 rollback；
- CLI/API/Broker 软件测试通过不能关闭 RC Gate；真实主机证据缺失时，任何“人工恢复成功”也只能作为事故处置记录。

## 2. 角色与四眼原则

| 角色 | 职责 | 禁止事项 |
|---|---|---|
| Release builder | 生成 immutable package、CycloneDX SBOM、manifest 与 Ed25519 signature | 不兼任本批 approver |
| Operator | 注册 Target、导入 package、提交/运行 Job、保存证据 | 不批准自己的 R3 request |
| Approver | 带外核对 target、host key、package/SBOM/signing-key digest 和影响范围 | 不修改 Job/spec |
| Incident owner | 决定停止扩批、reconcile 或 rollback | 不绕过 CAS/health check |

## 3. RC 冻结清单

每个架构分别冻结并保存：

- source commit、构建器版本和构建环境 image digest；
- package directory digest、`target-package.json`、`target-package.sig.json`；
- `target-package.cdx.json` 及其 signed manifest entry；
- Ed25519 signing key id 与独立核验的 public-key fingerprint；
- x86_64/AArch64 package manifest digest，不得跨架构复用；
- 目标 OS image/kernel/CPU、Rolo version、Python version、host-key fingerprint；
- rollout owner、approver、窗口、批次、停止条件和预期 current digest。

任一冻结字段变化都产生新的 RC，不允许覆盖原证据目录。

## 4. Canary 前检查

Controller 必须持有与目标 authorization-key pin 匹配的 Ed25519 签名密钥。私钥只允许 Controller 专用账号读取，
不得进入 Target package、SSH 传输、浏览器或 Codex 上下文：

```bash
export ROLO_DEPLOYMENT_AUTHORIZATION_KEY_ID=controller-authorization-2026
export ROLO_DEPLOYMENT_AUTHORIZATION_PUBLIC_KEY_PATH=/etc/rolo/trust/controller-authorization-2026.pub.pem
export ROLO_DEPLOYMENT_AUTHORIZATION_PRIVATE_KEY_PATH=/etc/rolo/private/controller-authorization-2026.pem
```

缺少 signer 或公私钥不匹配时，rollback Job 可以提交和审批，但 runner 必须在派发目标 mutation 前失败关闭。

```bash
robotctl target agent readiness

robotctl target connect assess \
  --target <canary-target> \
  --active-probe runtime-readonly \
  --idempotency-key rc-connect-<rc>-<target>

robotctl target job run --job-id <assessment-job-id>
robotctl target job get --job-id <assessment-job-id>
robotctl target job events --job-id <assessment-job-id>
```

必须确认 readiness 仍明确显示外部门禁，不能把静态报告当作放行依据。Connection Assessment 必须绑定预置
STRICT host key；任何 fingerprint mismatch 都停止 RC。

## 5. 导入、审批与 Canary 安装

```bash
robotctl target package import \
  --target <canary-target> \
  --source <immutable-package-directory>

robotctl target bootstrap submit \
  --target <canary-target> \
  --package-ref '<package-id>@<manifest-sha256>' \
  --requested-by <operator-principal> \
  --approver <approver-principal> \
  --expected-current-state present \
  --expected-current-manifest-sha256 <old-manifest-sha256> \
  --idempotency-key rc-bootstrap-<rc>-<target>

robotctl target approval decide \
  --approval-id <approval-id> \
  --principal <approver-principal> \
  --idempotency-key rc-approve-<rc>-<target> \
  --reason 'Verified target, host key, package, SBOM, signing key and expected current digest.' \
  --approve

robotctl target job run --job-id <bootstrap-job-id>
robotctl target job get --job-id <bootstrap-job-id>
robotctl target job events --job-id <bootstrap-job-id>
```

首次安装使用 `--expected-current-state absent`，并省略 expected-current digest。升级必须使用 `present` 和精确旧
digest；CAS mismatch 不得改参数重试，必须重新获取权威状态并重新审批。

Canary 成功的最低条件：Job `COMPLETE`、Bootstrap artifact `SUCCEEDED`、install result `ACTIVATED` 或同 digest
的 `ALREADY_ACTIVE`、健康检查成功，且目标 current digest 等于 RC manifest digest。

## 6. 观察与扩批

Canary 观察窗口内只运行已批准的只读 smoke/Adapt：

```bash
robotctl target adapt submit \
  --target <canary-target> \
  --active-probe runtime-readonly \
  --no-run-adapter-agent \
  --timeout-s 1800 \
  --idempotency-key rc-adapt-<rc>-<target>
```

建议批次为 `1 canary -> 同架构 10% -> 同架构 50% -> 同架构 100%`，x86_64 与 AArch64 分开判定。
每一批都使用独立 idempotency key、Approval 和证据目录。以下任一条件立即停止扩批：

- 任一签名、SBOM、host-key、target registration 或 CAS mismatch；
- Job 进入 `FAILED`、`BLOCKED`、`REQUIRES_RECONCILIATION` 或发生未知远端结果；
- 健康检查、只读 smoke、服务重启或资源预算失败；
- 同批目标出现不一致 current digest；
- 审计事件、receipt 或目标状态无法完整保存。

## 7. Rollback 判定与执行

Rollback request 必须冻结 target、当前 RC digest、previous digest、触发证据、requester/approver、expiry 和
expected-current CAS。执行前必须重新验证 previous package 的 manifest、SBOM、Ed25519 signature 与 health check；
成功后 current 必须等于 previous digest，原 RC 成为 previous，且产生不可变 Job/Event/receipt。

上述语义现由 strict `TargetRuntimeRollbackSubmission/JobSpec/JobArtifact`、独立 R3 Approval、Job checkpoint、
幂等 replay、fixed dispatcher 和 installer 软件测试共同覆盖。CLI 提交命令为：

```bash
robotctl target runtime rollback \
  --target <target> \
  --package-id <previous-package-id> \
  --expected-current-manifest-sha256 <current-rc-manifest-sha256> \
  --expected-previous-manifest-sha256 <previous-manifest-sha256> \
  --requested-by <operator-principal> \
  --approver <approver-principal> \
  --idempotency-key rc-rollback-<rc>-<target>

robotctl target approval decide \
  --approval-id <approval-id> \
  --principal <approver-principal> \
  --idempotency-key rc-rollback-approve-<rc>-<target> \
  --reason 'Verified target, current digest, previous signed release and incident evidence.' \
  --approve

robotctl target job run --job-id <rollback-job-id>
robotctl target job get --job-id <rollback-job-id>
robotctl target job events --job-id <rollback-job-id>
```

API 使用 authenticated `POST /v1/targets/{target_id}/runtime-rollback-jobs`；Session Agent 只能选择
`SUBMIT_RUNTIME_ROLLBACK` 并得到 `APPROVAL_REQUIRED`，不能决定审批。SSH 断线或 executor 异常发生在派发后时，
Job 必须进入 `BLOCKED/REQUIRES_RECONCILIATION`，禁止用相同或新 idempotency key 盲重跑。

也可用 `robotctl target tui --submit-runtime-rollback --target <target> --requested-by <operator-principal>` 打开有界
交互式表单。该表单只创建 Job 与 R3 Approval；独立审批和显式 `job run` 仍不可省略。

执行时 Controller 将 Approval 精确绑定到去除 proof 后的 rollback request digest，验证 signer 公私钥匹配后签发
短时 `ROLLBACK_TARGET_RUNTIME` proof。目标已安装 runtime 通过本地 authorization-key pin 验证 proof，再读取
previous package 或改变 current；runtime forced credential 继续拒绝 mutation。

该 proof 链的成功、缺失、错 action/target/Approval、过期和 signer mismatch 已有软件测试。RC rollback Gate 目前
仍阻塞于外部安全评审，以及 x86_64/AArch64 真实升级后 rollback、断线、Controller/目标重启和证据签字验收。

## 8. 每目标证据目录

```text
<rc>/<architecture>/<target>/
  environment.json
  target-profile-redacted.json
  package-manifest.json
  package-signature.json
  package-sbom.cdx.json
  connection-assessment.json
  approval-request.json
  approval-decision.json
  bootstrap-job.json
  bootstrap-events.jsonl
  install-result.json
  readonly-smoke.json
  rollback-request.json          # rollback 时必需
  rollback-result.json           # rollback 时必需
  checksums.sha256
```

证据必须 secret-closed；不得保存 SSH private key、Controller bearer、provider key 或未脱敏环境变量。

## 9. Runbook 冻结条件

只有以下全部完成，本文状态才能改为 `ACCEPTED`：

- 公开 rollback contract 与 CLI/API/TUI/GUI、Session Agent 接入并通过权限/审批审计；
- Linux x86_64 与 AArch64 各完成一次真实 upgrade + rollback；
- 覆盖网络中断、Controller 重启、目标重启、健康检查失败和 CAS 冲突；
- 保存第 8 节完整证据并由独立 reviewer 签字；
- W10 矩阵对应行从 `NOT_VERIFIED` 更新为环境绑定状态。
