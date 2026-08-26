# W10 真机、故障注入与生产就绪矩阵

状态：`IN_PROGRESS_AUTOMATED_EVIDENCE_CONTRACT`
基线：Rolo `main@a75ea0b`，开发分支 `codex/unified-agent-deployment`
原则：软件测试只能证明软件边界；真实 provider、真实 sshd、CPU 架构、ACL、网络与重启证据不得自我声明。

## 1. 状态定义

| 状态 | 含义 |
|---|---|
| `SOFTWARE_VERIFIED` | 严格契约、单元/集成测试和本机构建已验证，但不代表真机通过 |
| `NOT_VERIFIED` | 尚无与指定环境绑定的真实验收证据 |
| `BLOCKED` | 已执行并确认前置条件或结果不满足 |
| `ACCEPTED` | 指定环境中的自动化证据与人工验收记录均齐全；当前开发切片不签发该状态 |

`robotctl target agent readiness` 只计算本机静态配置和命令契约。外部门禁固定返回 `NOT_VERIFIED`，当前版本
没有允许用户通过布尔参数或自然语言把它改成 `PASSED` 的入口。对应 authenticated API 为
`GET /v1/session-agent/readiness`。

## 2. Session Agent W9/W10 门禁

| 门禁 | 当前证据 | 当前状态 | 关闭条件 |
|---|---|---|---|
| feature flag 与独立 provider credential | readiness 配置摘要，不输出 key | `SOFTWARE_VERIFIED` | 生产配置审计 |
| HTTPS provider endpoint | URL 结构检查 | `SOFTWARE_VERIFIED` | 企业 endpoint/TLS 策略复核 |
| Codex executable | PATH 可解析性，只返回布尔值 | `SOFTWARE_VERIFIED` | 固定版本、来源和二进制签名/SBOM |
| ephemeral/read-only/空环境命令契约 | argv digest 与契约测试 | `SOFTWARE_VERIFIED` | 真实进程 ACL 复核 |
| dedicated OS user/container | 无 | `NOT_VERIFIED` | Linux 上验证 uid、mount、network、HOME、Controller store ACL |
| real provider acceptance | 提供 opt-in smoke，默认不运行 | `NOT_VERIFIED` | 独立 key 下通过 smoke、失败/超时/重试和模型版本回归 |
| real SSH prompt injection | 结构化 broker 已限制动作，但无真实恶意目标 | `NOT_VERIFIED` | 真实 sshd 注入 banner/README/log/stdout，证明不能扩大 catalog/target/approval |
| multi-worker failure injection | 两个独立 Controller 进程对同一 session command 只提交一个 receipt；同主机 owner 硬退出后可回收 guard | `NOT_VERIFIED` | 共享文件系统/多主机 worker + kill/restart + cancel/reconcile 故障注入 |
| Linux x86_64 | 无真机证据 | `NOT_VERIFIED` | Ubuntu/Debian x86_64 全链验收 |
| Linux ARM64 | 无真机证据 | `NOT_VERIFIED` | Ubuntu/Debian ARM64 全链验收 |

真实 provider selector smoke：

```bash
export ROLO_RUN_REAL_SESSION_AGENT=1
export ROLO_SESSION_AGENT_API_KEY='<dedicated-provider-key>'
export ROLO_SESSION_AGENT_MODEL='<reviewed-model>'
pytest -q tests/test_real_session_agent.py
```

该 smoke 只证明 provider 能在隔离配置下返回 bounded schema，不证明 SSH、部署副作用或生产 readiness。

真实 sshd fixture 也是 opt-in，要求目标已安装受审核的 `robotctl`，并分别提供 provisioning、bootstrap、runtime
三个 credential purpose 所需的固定入口：

```bash
export ROLO_RUN_REAL_SSH_ACCEPTANCE=1
export ROLO_REAL_SSH_HOST='<target-host>'
export ROLO_REAL_SSH_PORT=22
export ROLO_REAL_SSH_PROVISIONING_USER='<existing-admin-user>'
export ROLO_REAL_SSH_PROVISIONING_IDENTITY_FILE='<absolute-admin-private-key-path>'
export ROLO_REAL_SSH_BOOTSTRAP_USER='<bootstrap-forced-command-user>'
export ROLO_REAL_SSH_BOOTSTRAP_IDENTITY_FILE='<absolute-bootstrap-private-key-path>'
export ROLO_REAL_SSH_RUNTIME_USER='<runtime-forced-command-user>'
export ROLO_REAL_SSH_RUNTIME_IDENTITY_FILE='<absolute-runtime-private-key-path>'
export ROLO_REAL_SSH_KNOWN_HOSTS='<absolute-known-hosts-path>'
export ROLO_REAL_SSH_HOST_KEY_SHA256='SHA256:<independently-verified-fingerprint>'
export ROLO_REAL_SSH_TARGET_ID='wheeltec'
export ROLO_REAL_SSH_PACKAGE_ID='rolo-runtime'
export ROLO_REAL_SSH_PACKAGE_MANIFEST_SHA256='<64位小写摘要>'
pytest -q tests/test_real_ssh_target.py
```

该 fixture 不使用 fake transport：provisioning/runtime 使用固定 `robotctl target-executor inspect` typed protocol，
bootstrap 使用固定 capability protocol。测试文件存在或默认 skip 都不构成真实 SSH 验收证据；只有在
指定 Linux image/主机上保存测试报告与环境 digest 后，才允许推进相应矩阵行。

注册三阶段身份后，可用产品 CLI 生成 secret-closed 的自动化 evidence receipt：

```bash
robotctl target acceptance real-ssh \
  --target wheeltec \
  --environment ubuntu-2404-x86-canary-01 \
  --architecture x86_64 \
  --os-image-sha256 '<64位小写摘要>' \
  --package-id rolo-runtime \
  --package-manifest-sha256 '<64位小写摘要>' \
  --acceptance-suite tests/test_real_ssh_target.py \
  --test-report ./evidence/real-ssh.junit.xml \
  --output ./evidence/w10-real-ssh.json
```

receipt 绑定 target/connection、endpoint、known_hosts、host-key pin、三阶段身份、OS image、package manifest、
suite 文件、JUnit report、目标侧已校验的 current runtime index 投影及每次 typed request/result 的摘要；current 投影
只含 package ID/version/manifest，不含目标 install path。声明 package/manifest 与实际 current 不一致时失败关闭。
receipt 不保存 host、credential reference、known_hosts 路径、测试用例名称、stdout/stderr 或密钥材料。
JUnit 必须至少实际执行四个用例；全 skip、failure、error、超限、DTD/entity
或摘要错配都会令自动门禁失败。
自动探测全通过时只得到 `automated_result=PASSED`；`matrix_status` 仍固定为 `NOT_VERIFIED`，
`manual_review_required=true`、`production_ready=false`。CLI 在任一自动门禁失败时仍先写 receipt，再以非零状态退出。

`.github/workflows/w10-real-ssh-acceptance.yml` 提供只允许从 `main` 手动触发、受 GitHub Environment 审批和固定
`self-hosted/linux/rolo-w10/rolo-w10-<architecture>` label 约束的入口。目标 profile、三个身份路径和 SSH pin
必须预置在受保护 runner；JUnit 与 receipt 只写入 runner 上 `ROLO_W10_EVIDENCE_DIR/<run-id>-<attempt>/`，当前不会
自动上传 GitHub Artifact。将证据导出到集中存储属于独立的数据外发决策，必须先确定目的地、保留期和脱敏策略。

## 3. W10 平台与故障矩阵

| 场景 | 当前状态 | 必须保存的权威证据 |
|---|---|---|
| Ubuntu/Debian x86_64 | `NOT_VERIFIED` | OS image digest、kernel、Rolo/package digest、完整 E2E report |
| Ubuntu/Debian ARM64 | `NOT_VERIFIED` | 板卡/SoC、OS image digest、kernel、Rolo/package digest、完整 E2E report |
| 无外网目标 | `NOT_VERIFIED` | network policy、离线 package/SBOM/signature、bootstrap transcript digest |
| 非 root 目标 | `NOT_VERIFIED` | uid/gid、文件权限、无 root 写入证明 |
| sudo 交互审批 | `NOT_VERIFIED` | Approval request/decision/capability digest 与 sudo argv 审计 |
| SSH jump host | `NOT_VERIFIED` | proxy profile、两段 host-key pin、连接与失败证据 |
| host key rotation | `NOT_VERIFIED` | old/new pin、独立批准、mismatch/rollback 测试 |
| 网络抖动/断线 | `NOT_VERIFIED` | 注入时间线、Job/Event、远端状态查询、reconciliation disposition |
| 磁盘不足 | `NOT_VERIFIED` | 注入阈值、staging 清理、current index 不变证明 |
| 中途重启 | `NOT_VERIFIED` | kill 点、journal、snapshot recovery、未知副作用处理 |
| ROS workspace | `NOT_VERIFIED` | ROS distro/domain/runtime-context/describe attestation |
| 非 ROS workspace | `NOT_VERIFIED` | secret-closed runtime-context/describe attestation |
| LeRobot editable CLI over SSH | `NOT_VERIFIED` | frozen Bundle、`.pth`、sandbox、`describe`/`--help`、Gate 全链 digest |
| Operation-scoped PATH | `NOT_VERIFIED` | 选中/未选中 CLI 对照与 target attestation |
| interpreter symlink/version alias | `NOT_VERIFIED` | resolved interpreter、venv identity、拒绝漂移用例 |
| unsafe editable `.pth` | `NOT_VERIFIED` | HOME/祖先/无 marker 三类拒绝证据 |
| ML address-space/process budget | `NOT_VERIFIED` | 不足时 blocker、批准调整、cgroup/rlimit 观测 |
| 多目标并行 | `NOT_VERIFIED` | 不同 target 并行时间线与无共享状态污染证明 |
| 单目标互斥 | `NOT_VERIFIED` | 多 worker 冲突 lease 与幂等 replay 证明 |
| upgrade/rollback | `NOT_VERIFIED` | signed package、expected-current CAS、current/previous 结果 |
| enrollment rotation | `NOT_VERIFIED` | old-key transition、new pin、旧 bundle 拒绝、断电恢复 |

## 4. W10 交付物审计

| 交付物 | 当前状态 | 证据位置/下一步 |
|---|---|---|
| 真机验收矩阵 | `SOFTWARE_VERIFIED` | 本文；所有真实环境行仍为 `NOT_VERIFIED` |
| E2E SSH server fixture | `IN_PROGRESS` | 已有三阶段身份 opt-in 真实 sshd 测试、JUnit-bound receipt 和受保护 self-hosted 手动工作流；当前环境默认 skip，仍需 Linux container/VM 报告，不接受 fake transport 替代 |
| chaos/failure-injection tests | `IN_PROGRESS` | 已有 Job/journal/cancel、双进程 command replay、同主机 owner 硬退出 guard 回收；待共享文件系统、多主机、网络和磁盘故障注入 |
| installer SBOM 和签名验证 | `SOFTWARE_VERIFIED` | builder 固定生成 CycloneDX 1.6 文件级 SBOM；SBOM digest/role 纳入 Ed25519 manifest，installer 严格交叉验证；待真实 RC 保存发行验签报告 |
| 安全评审和操作手册 | `IN_PROGRESS` | target runtime rollback 的短时 proof、精确 Approval scope、目标本地 key pin 与只读 runtime credential 边界已记录并软件验证；待外部评审和真机证据 |
| RC rollout/rollback runbook | `IN_PROGRESS` | authenticated rollback Job、CLI/API/独立 GUI/Broker/有界交互式 TUI、R3 Approval、目标侧 proof、双 CAS 与未知结果对账已软件验证；待外部安全评审和真实 x86_64/AArch64 upgrade+rollback 后冻结 |

## 5. 生产判定

当前 `production_ready=false`。只有上述外部门禁均由目标环境绑定、可复核、secret-closed 的证据关闭后，才允许
设计签名 acceptance receipt；在此之前 GUI、TUI、CLI 与 API 都必须继续显示开发预览或 `BLOCKED/NOT_VERIFIED`。
