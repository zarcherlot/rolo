# Rolo 统一 Agent 部署与远程适配开发计划

状态：`ACTIVE_W5_SOFTWARE_CORE_IN_PROGRESS`

基线：`main@666f35c`（已合入 PR #17）

计划日期：`2026-08-25`

## 0. 决策摘要

本计划接受以下产品方向：

1. 用户只面对一个 Rolo 会话 Agent；该 Agent 可以连续完成对话、目标检查、部署、注册、
   证据采集和 Adapt。
2. 会话 Agent 与部署执行器可以属于同一产品主体、同一任务甚至同一服务进程，但必须保留
   工具权限、凭据、审批和审计边界。
3. 自然语言不要求先转换成用户可见的完整静态计划；真正执行的工具调用、状态变更、审批、
   重试和回滚必须具有结构化契约。
4. 目标机逻辑上仍需完成本地 Collector enrollment。用户不应再被要求手工运行
   `robotctl target-evidence collector-init`；Local 或 SSH Target Executor 在目标机上幂等执行。
5. CLI、TUI、GUI 和自然语言共用同一 Application Command、Job 和 Event 层，不分别实现
   部署逻辑。
6. SSH 第一阶段同时承担连接和 bootstrap；部署完成后切换到最小权限的目标端入口。
7. Adapter Agent 不获得部署 SSH 凭据，也不成为远端管理员。
8. 现有 Adapt、Discovery、Wiki、Operation Mapping、Gate、Catalog、State Graph 和 release
   保持权威，不因新交互层降低证据或门禁要求。

这是一项产品控制面扩展，不是重写 Adapt 核心。

### 0.1 PR #17 重新评审结论

本计划已根据 PR #17 `feat(adapt): complete and harden LeRobot integration` 的 5 个新增提交
重新评审。该 PR 已完成：

- 从当前 Bundle Operation 选中的目标 CLI Route 派生有界 `PATH`；
- 将经过约束的 editable Python root 显式转换为 `PYTHONPATH`；
- 在 bubblewrap 中只读挂载选中的虚拟环境、解释器和必要依赖；
- 为 ML-backed CLI 提供可配置的 address-space 和 process/thread budget；
- 固定 Adapter `invoke` ABI，同时明确 Promotion 只运行 `describe`、不得用 `invoke` 探测；
- 在 Linux CI 中让真实 editable LeRobot CLI 通过 production sandbox 验收。

重新评审后的判断：

1. PR #17 显著提高了 Local Target Runtime、Operation-scoped runtime context 和 sandbox 的复用
   价值，不应在统一部署项目中另建一套沙箱或 CLI 运行上下文。
2. PR #17 同时暴露出 SSH 模式的关键位置问题：目标 CLI、virtualenv、editable source 和解释器
   是目标机绝对路径，控制器不能用本机 `Path.exists()`、本机挂载或同路径副本替代目标校验。
3. 因此 `CONTROLLER + SSH` 的正式形态必须把 frozen release 的目标侧 `describe` 和授权后的
   `invoke` 放在目标机 production sandbox 中执行。Adapter Agent 和独立 Gate 可留在控制器，
   但 Gate 必须消费目标侧按 release digest 绑定的 `describe` 结果。
4. Promotion 仍只执行 `describe`。SSH bootstrap、远程 Gate 或 GUI 不能为了验证连接而调用
   `invoke`，更不能通过摄像头枚举、运动或其他业务副作用证明部署成功。
5. PR #17 的真实 LeRobot CI 是重要软件基线，但仍不连接 SSH 真机、不枚举摄像头，也不构成
   远程部署、真机行为或安全验收。

据此，原 W5 从“远程 Workspace 集成”升级为“位置感知 Runtime Context、目标侧 Sandbox 与
Release 部署”，并成为 Phase B 的硬门槛；MVP 工程量相应上调。

### 0.2 W0 实施结果

W0 已在 `codex/unified-agent-deployment` 完成首批交付：

- [`UNIFIED_AGENT_DEPLOYMENT_W0_DECISIONS_ZH.md`](UNIFIED_AGENT_DEPLOYMENT_W0_DECISIONS_ZH.md)
  冻结九项架构决策；
- [`SSH_AGENT_BOOTSTRAP_THREAT_MODEL_ZH.md`](SSH_AGENT_BOOTSTRAP_THREAT_MODEL_ZH.md)
  固定资产、信任边界、安全不变量、威胁、审批和恢复规则；
- 新增 `TargetProfile`、`TargetConnectionProfile`、`DeploymentCommand`、`DeploymentJob`、
  `DeploymentEvent` 和 `ApprovalRequest` 严格模型；
- 六个模型已进入 canonical Schema export 和 tracked-schema 漂移测试；
- W0 只冻结契约，没有提前实现 SSH、Credential Provider、Job runner、installer 或 v4 密码学。

### 0.3 W1 实施结果

W1 已在同一分支完成：

- `TargetProfileRegistry` 使用原子写入分别持久化 Target/Connection profile，加载时再次执行
  strict Schema、文件名身份、交叉引用、trust-level 和 secret-field 检查；
- `CredentialProvider` SPI、`CredentialResolver` 和 executor-only `ResolvedCredential` 已建立，
  profile、Command、日志表示只出现 credential reference；
- `ApplicationCommandBus` 使用 digest-bound `CommandEnvelope` 验证执行参数，缺失、替换或摘要不匹配
  均失败关闭；
- `AdaptStartParameters` 覆盖当前 `adapt start` 的路径、evidence 和执行参数，canonical renderer
  能复现等价 CLI；
- 当前本地及已有 pinned-collector `adapt start` 已通过 Command Bus 执行，原 JSON 输出和阻塞退出码
  保持兼容；
- `interaction_surface` 作为 provenance 保留，但不参与执行语义 digest，因此 CLI/TUI/GUI/NL 可复现
  同一 Command digest；
- W1 模型进入 canonical Schema export，并由 Registry/Credential/Command Bus/CLI compatibility 测试保护。

### 0.4 W2 实施结果

W2 已完成软件实现和 conformance 验证：

- 新增严格的 `TargetInspectionRequest/Result`、统一错误码和 `TargetExecutor` protocol；
- `LocalTargetExecutor` 与 `SshTargetExecutor` 返回相同结果模型，目标侧固定入口为隐藏的
  `robotctl target-executor inspect`；
- SSH 只发送 strict JSON stdin，远程命令固定，Agent operand 不进入 SSH remote command 字符串；
- executor 生成独立 SSH config，支持 Port、Identity、ProxyJump 和每跳 known_hosts；命令行再次
  强制 `BatchMode=yes`、`StrictHostKeyChecking=yes`、无 PTY、无 forwarding；
- `expected_host_key_sha256` 在连接前与目标 host/port 对应的 known_hosts key 绑定，CA profile
  要求对应 `@cert-authority` 条目；
- subprocess stdout/stderr、timeout、cancel、非零退出、spawn、协议错误和进程树清理均有界且有
  确定错误码；SSH 退出 `255` 与目标固定命令普通非零退出分开分类；
- 子进程环境使用 allowlist，credential material 只在 executor 内解析，错误和协议校验不回显
  未知输入值；
- W2 Schema 已进入 canonical export，Local/SSH contract、strict SSH argv/config、ProxyJump、
  fingerprint、错误分类、redaction 和 companion CLI 均有测试覆盖。

W2 当前结论为软件验证；真实 sshd、断网和真机矩阵仍属于 Gate B/W10，不能由 injected transport
conformance 替代。

### 0.5 W3 当前实施结果

W3 的软件核心已完成，当前结论仍不代表真实 SSH Bootstrap 或主机级安装验收完成：

- 新增 `TargetPackageManifest`、`TargetPackageSignature`、`TargetPlatformFacts`、
  `TargetPlatformPreflight`、`BootstrapPlan`、`TargetInstallIndex` 和
  `TargetBootstrapInstallResult` 严格契约，并纳入 canonical Schema export；
- 制品清单覆盖 Linux x86_64/AArch64、Python 版本、bubblewrap/namespace、显式
  `PATH`/`PYTHONPATH`/virtualenv 能力，以及 address-space/process budget 要求；
- preflight 将能力不足转换为稳定、去重、排序的结构化 blocker；dry-run plan 显式列出
  upload、verify、install、activate、health-check、rollback、风险等级和逐项 sudo 审批摘要；
- `RUNTIME_CAPABILITIES` 通过固定脚本实际检查目标 Python、bubblewrap、user/mount/network
  namespace、显式 `PYTHONPATH`、virtualenv、RLIMIT_AS 和进程/cgroup 预算；结果严格解析为
  `TargetPlatformFacts`，协议损坏与传输错误使用确定错误码；
- 首次 SSH 预检不再循环依赖目标机已安装的 `robotctl`：只对该固定工具使用产品内置的
  `python3 -` stdin 协议，仍强制 host-key pin、BatchMode、无 PTY/forwarding 和有界输出；
- 新增 `robotctl target bootstrap dry-run` 与 `TargetBootstrapPlanner` API；它从注册的 Local/SSH
  TargetProfile 构造执行器，使用 `SSH_BOOTSTRAP` credential purpose，验证制品后才连接目标，
  并只输出 target-observed plan，不执行上传、sudo、安装或激活；
- 使用 detached Ed25519 签名和 pinned public-key verifier；私钥只从权限受限的本地文件读取，
  key/制品路径拒绝符号链接，错误不回显密钥材料；
- 离线目录制品安装执行严格文件集、size/digest/signature 校验，先写 staging，再进行健康检查和
  current index compare-and-swap；中断或健康检查失败不会激活不完整版本；
- 新增 `TargetPackageTransferRequest/Result` 与 `TargetPackageUploader`：控制器只在完整验签后发送
  有界 Base64 chunk，每次绑定 manifest/file/chunk digest、相对路径和 offset；Local/SSH 共用契约；
- SSH preinstall transfer 使用产品固定、Base64 封装的 standalone Python handler，request 只经
  stdin 传输，remote command 不包含 target/path/chunk；目标写入固定 incoming root，按文件持久化
  offset，支持连接中断续传、offset reconciliation 和完整重复上传零新增字节；
- 新增 `TargetBootstrapExecutionRequest/Result`、目标侧 verify/install/activate/health/rollback
  服务和 `TargetBootstrapOperator`；同一主体按“控制器完整验签 -> 可续传上传 -> 目标端二次验签
  -> preflight -> 事务安装”的固定顺序执行，并绑定 target/package/manifest/release-key digest；
- 目标端 preinstall launcher 只定位固定 incoming root 中的 digest-bound 包，校验 manifest 与
  entrypoint 后调用签名包内的 `target-executor bootstrap`；目标 companion 再次校验完整文件集、
  Ed25519 签名、能力和 CAS 状态，健康检查成功后才原子切换 current；
- 发布公钥 pin 使用规范化 Ed25519 raw public key 的 SHA-256，而非 PEM 文本字节摘要；TargetProfile
  可同时固定 key id、控制器公钥绝对路径和规范化 digest，执行 request/result 继续携带并核对该 pin；
- 新增 prepared-runtime 到签名目录制品的确定性 builder，覆盖 Linux x86_64/AArch64、稳定文件
  排序/角色/mode、metadata 冲突、symlink、嵌套输出和私钥误打包防护；W10 在此基础上固定生成
  `target-package.cdx.json` CycloneDX 1.6 文件级 SBOM，将其 digest/role 纳入 Ed25519 manifest，
  installer 会把 SBOM 内容与所有非 SBOM 文件及 package metadata 严格交叉验证；
- 新增 reviewable systemd 与 OpenSSH `authorized_keys` 模板契约。systemd 只监听 loopback 并启用
  `NoNewPrivileges`、`ProtectSystem`、`ProtectHome`、network deny 等限制；运行期密钥强制进入
  `target-executor dispatch`，仅允许已安装的 inspect 以及 STATUS/HEALTH，禁止 mutation 和
  `python3 -` 任意 stdin 脚本；
- 相同 version + manifest digest 重复安装返回 `ALREADY_ACTIVE`，升级保留 previous release，
  rollback 会重新校验目标版本并原子切换；
- 新增三阶段 SSH identity、`TargetHostTemplateBundle/v2`、固定 bootstrap dispatcher、manifest-verifying
  runtime launcher 和 `TargetHostProvisioningPlan/v1`；主机账号、目录、两把 forced-command key、dispatcher、
  launcher、systemd unit、daemon-reload 与 enable 均以明确 path/owner/group/mode/digest/argv 进入 R3 范围；
- 新增 `PROVISION_HOST` 持久 Job、retry-stable submission intent、spec/artifact、`USE_SUDO` Approval 与
  per-target runner；执行器只用 provisioning credential，把冻结计划经 stdin 交给固定 root installer，支持
  compare-and-swap、幂等 `ALREADY_CURRENT`、artifact replay，未知远端结果进入 reconciliation；
- `robotctl target host plan/submit`、`target approval decide`、`target job run` 与认证 API
  `POST /v1/targets/{target_id}/host-provisioning-jobs` 已接入；API 回执不暴露 credential、host path、
  authorized_keys 内容或 installer script；通用 TUI/Workbench 可查询 Job 和 Approval；
- 新增固定的特权只读 host observer 与 `RECONCILE_HOST` 持久 Job。它使用独立 provisioning 身份和
  R2 `USE_SUDO` Approval，对 commit marker、runtime identity、SSH 目录、dispatcher、launcher、
  authorized_keys、systemd unit 与 enable 状态做 digest-bound 比较，不重放 installer；`EXACT` 才把原
  UNKNOWN checkpoint 闭合为 COMPLETE，`NOT_COMMITTED` 仅解锁新 attempt，different/drift 保持阻断；
- `robotctl target host reconcile --job-id ...` 与认证 API
  `POST /v1/jobs/{job_id}/host-reconciliation-jobs` 已接入；observation artifact 和原 Job 修复均可崩溃恢复，
  幂等重放不会重复远端观测；
- 新增 R3 `ROLLBACK_HOST_CONFIGURATION`：`robotctl target host rollback` 和认证 API 引用当前/旧两个已完成
  host configuration Job，用当前 registration 重建旧 key/template 配置并绑定 current plan CAS；执行复用固定
  installer，不删除 runtime 用户、数据或制品；
- 新增激活后 R2 `START_TARGET_SERVICE` Job：同时绑定完成态 host/Bootstrap Job、registration、host plan、
  active runtime manifest 和固定 unit，目标侧复核后才运行固定 `systemctl start`；连接中断进入 UNKNOWN；
- 新增 R2 STATUS-only `RECONCILE_TARGET_SERVICE`：ACTIVE 闭合成功、INACTIVE 解锁新 attempt、host/runtime
  digest 漂移继续阻断；CLI/API 与统一 runner 均已接入，模型不能提供 unit 或任意 shell；
- W0-W3 新增路径的定向回归与静态检查已经通过；完整仓库回归以本轮最终检查结果为准。

W3 剩余的是主机与发布工程真机闭环：产出真正自包含的 x86_64/AArch64 runtime artifact，验证已审查
主机事务在真实 root/systemd/OpenSSH 上安装账号/systemd/authorized_keys，完成 bootstrap 身份向 runtime
身份切换及激活后首次启动，并覆盖断网、重连、升级、回滚和服务重启。standalone handler 的
Linux conformance 测试在非 POSIX 开发机跳过，必须由 Linux CI 和 Gate B/W10 的真实 SSH 目标矩阵
补证；当前 builder 只接受已经准备好的 runtime tree，不负责解析或下载依赖。

### 0.6 W4 当前实施结果

W4 已进入软件核心实施，当前完成：

- 新增 `CollectorConfigurationV4`、`CollectorDescriptorV4`、challenge attestation、controller pin、
  target identity record/index、rotation transition 及 `TargetEnrollmentRequest/Result` 严格契约；
- 目标本地以 Ed25519 生成私钥，私钥只写入受限 identity generation 目录，结果、descriptor、pin、
  Command 和日志均不含私钥路径或材料；active index 使用跨进程锁和原子替换，失败前生成的 generation
  不会成为 current，重复/并发 enrollment 只产生一个 active identity；
- 每次 ENROLL/STATUS/ROTATE 都使用 request digest、challenge nonce、issued/expires 和新 key 签署
  proof-of-possession；控制器验证 freshness 和签名后才固定 public key；
- rotation 使用 compare-and-swap old collector pin，新 descriptor 由旧 Ed25519 identity 签署 transition，
  target current 与 controller pin 都保留 transition record；
- `LocalTargetExecutor` 与 `SshTargetExecutor` 共用 `TargetEnrollmentService`，mutation 只允许
  `SSH_BOOTSTRAP` credential；运行期 forced command 只允许 enrollment STATUS；
- 新增 `robotctl target enroll`，通过 Application Command Bus 生成 digest-bound canonical Command，
  并把验证后的 descriptor/configuration/public key 原子写入 controller pin registry；
- 新增 Ed25519 `TargetEvidenceBundleV4`、collection request/result 和 verifier；v2 HMAC 采集与验签继续
  走原兼容路径，未被自动迁移；v4 bundle 已覆盖 robot/target/collector/host/config/key、nonce、
  requested layers、freshness、payload digest 和 detached signature；
- Adapt Journey 在存在同 target/robot 的 v4 controller pin 时优先使用 Local Executor 采集并验证
  Ed25519 bundle，写入的 Journey summary 显式记录 `ED25519_V4`、target、descriptor digest 和 key ID；
  没有 v4 pin 的已有安装继续走 legacy HMAC deployment，不发生静默迁移；
- v4 目标侧采集已接入 Local Executor 和 bootstrap companion。由于证据可能包含敏感主机信息，
  在 W6 scoped authorization capability 完成前，运行期 SSH forced-command 明确拒绝 evidence-v4，
  不能仅因操作只读就扩大 runtime credential 权限；
- 上述 persisted/public 模型已进入 canonical Schema export，并有 tamper、replay、expiry、identity/
  host mismatch、并发、interrupt、rotation、Local/SSH credential boundary 和 legacy HMAC 回归覆盖。

W4 软件核心已完成自动配置发现、legacy `collector-init` 恢复入口说明，以及 proof-bound runtime
evidence/SSH Adapt 的目标侧和控制器二次验签。剩余门禁是真实 sshd 下的 enroll/rotate/collect/reconcile、
W3 身份切换和 W10 平台矩阵；不能把软件注入测试视为生产批准或真机证据。

### 0.7 W5 当前实施结果

W5 已完成位置、证明、签名传输、非激活暂存、Gate 收据和原子激活/回滚的软件核心，但尚未完成
真实 Linux/SSH 与生产授权闭环：

- 新增 `TargetWorkspaceRef`、`TargetWorkspaceFile` 和 `TargetWorkspaceManifest`；manifest 只能由
  目标端对显式选择的普通文件生成，拒绝绝对/父级路径、symlink、非普通文件、单文件/总大小和
  文件数超限，content digest 不包含观察时间且与选择顺序无关；
- 新增 Linux-first `LocatedRuntimeContext`、secret-closed `TargetObservedRuntimeEnvironment` 和
  `AdapterSandboxBudget`；控制器只验证目标绝对路径语法，不调用本机 `Path.exists()`，真正执行前
  才在目标端物化为 PR #17 的 `AdapterRuntimeContext` 和 `BoundedAdapterRunner` 预算；
- 新增 `TargetDescribeRequest`、严格 `TargetDescribeOutput` 和 `TargetDescribeAttestation`；证明由
  当前 Collector Ed25519 key 签署，绑定 target/robot/collector、request/nonce/freshness、release、
  Bundle、Runtime Context、sandbox profile、完整 allowlisted output digest 和 operation mapping；
- Controller verifier 要求当前 public-key pin、请求、输出和期望 Bundle mapping 全部一致；篡改、
  replay、过期或任一 digest 不匹配均失败关闭；`describe` 契约没有 `invoke` 字段或执行入口；
- 新增目标侧 `execute_target_describe` 服务：对 frozen release 执行 exact file-set、逐文件 digest、
  Release/Bundle file binding、目标 entrypoint 和实际 sandbox launcher+预算摘要校验，然后只向注入的
  PR #17 `AdapterRunner` 发送 `describe`；输出通过 allowlist 后才由 Collector 签名；
- 新增签名的 `AdapterReleaseTransferManifest`、断点续传和目标侧 `AdapterReleaseStager`：只传输 frozen
  release 精确文件集和一个位置化 Runtime Context；目标再次验签、逐文件复核并原子落入只读 staged
  目录，上传或暂存成功都不会写入 `current.json`；
- 新增 Local/SSH companion 的 `adapter-release-stage`、`adapter-release-describe` 和
  `adapter-release-activate` typed protocol。目标从 release identity 和摘要推导 staged path，拒绝控制器
  指定任意执行目录；当前 runtime forced credential 明确拒绝这三个命令，只允许 bootstrap credential，
  等待 W6 scoped authorization；
- 新增短时效、签名的 `AdapterReleaseGateReceipt`：Controller 先验证 Collector attestation、请求、
  release/Bundle/Runtime/sandbox/output/freshness，再签发 PASSED 收据；目标激活前复核 Gate 收据、签名
  transfer 和 staged bytes；
- 新增 `AdapterReleaseActivator`：在锁内原子切换 `current.json`，同一 transfer 幂等，二次激活保留
  previous，并以 expected-current CAS 执行 rollback；篡改、过期、路径错配和 CAS 冲突均不得改变 current；
- 新增 `TargetProjectEvidenceRequest/Snapshot`：Controller 只能声明有界、排序、无通配符的相对候选
  文件；目标端判断 optional/required、普通文件、symlink、范围和 digest，未声明文件不会被递归枚举或进入
  manifest。该协议当前只允许 bootstrap credential，等待 W6 对源码读取授权建模；
- 新增只读 `adapter-release-status` 和 Controller reconciliation：目标重新验签 current、previous 与期望
  staged release，只返回 identity/digest/provenance，不返回 staged 绝对路径；Controller 将该快照与权威
  `AdapterReleaseIndex` 绑定，输出 NONE、deploy+activate、activate-staged、rollback 或 manual-review 计划，
  并携带下一步必须使用的 current CAS digest。状态不可验证时保留 unknown/blocked，不自动重放写操作；
- `adapter-release-status` 可由 runtime forced credential 调用；project evidence 现在仅在绑定独立 R2 Approval、
  短时 `READ_PROJECT_EVIDENCE` proof 和显式候选范围时允许固定 typed command；stage/describe/activate 仍不能通过
  runtime forced credential；
- 新模型已进入 canonical Schema export，并覆盖路径逃逸、symlink、大小边界、续传、篡改、中断清理、
  Gate freshness、激活幂等、rollback CAS、SSH request/response binding 以及“describe 不调用 invoke”的
  端到端软件测试。

尚未完成：使用 Linux production sandbox conformance fixture 验证 staged `describe`、真实
sshd/断网/重连矩阵、公开部署/状态/reconcile CLI，以及 W6 对 approval principal/command/expiry、项目
证据读取范围和目标侧 release-key pin 的生产验证。当前
W6 已把裸 `approval_id` 替换为目标可验证的短时签名 proof，但 authorization key 的首次安装/轮换仍需
接入正式 Bootstrap Job。不能把注入式 runner、fake SSH transport 或 API 级激活测试解释为生产远程
Adapter 已部署。

### 0.8 W6 首批实施结果

W6 已完成 Job/Event/Approval/Recovery 与 W5 请求级签名授权的软件核心；W7 继续接入正式 Bootstrap
信任锚事务、首个实际 Job handler 和 HTTP 路由：

- 新增 `DeploymentJobStore` 与 `DeploymentJobRecord`：Job snapshot 通过同目录原子替换写入，按
  idempotency key 去重并拒绝同 key 的不同 command digest；每次写入带 revision、attempt、checkpoint、
  cancel/recovery disposition 和最终 artifact refs；
- 新增 hash-chain、append-only `DeploymentEventRecord`。事件先持久化，内含有界 recovery snapshot；若
  进程在 journal fsync 后、Job snapshot 替换前崩溃，重启读取会验证整条链并从最后事件重放 snapshot；
- 事件 summary 统一成单行、有界输出，并对 PEM、Bearer、password/token/secret/API key/private key
  常见形态做 redaction；artifact 只能使用排序、去重的 `artifact://` 引用；
- 新增 `DeploymentStepCheckpoint`、forward-only state transition、per-target interprocess lease、
  start/complete/fail、cancel/resolve、retry/resume，以及 remote state unknown 时强制
  `BLOCKED + REQUIRES_RECONCILIATION`；
- 新增 restart recovery：非终态 Job 在进程重启后不会假装继续运行；远端写阶段或运行中远端 checkpoint
  进入 reconciliation，安全的本地/连接阶段标为 resumable；
- `ApprovalRequest` 现在绑定 requester principal、独立 approver principal、job/target/command digest、
  action、精确 `authorization_scope_sha256` 和最长 24 小时 expiry，并禁止自批；`ApprovalDecision`
  作为不可变独立记录，verification 要求 APPROVED、principal、全部 identity/digest/action 和当前时间一致；
- 新增独立 Ed25519 authorization 信任域。Controller 只能从已验证 Approval 签发最长 10 分钟的
  `DeploymentAuthorizationGrant/Proof`，并绑定 approval/decision/job/target/command/action、approver、
  request schema 与去除 proof 后的完整 request payload digest；Approval scope 与 payload 不一致时拒绝签发；
- 新增目标本地、write-once 后仅允许 bootstrap CAS 替换的 `DeploymentAuthorizationKeyRegistry`。目标验证
  只读取本地 pin，不接受请求随附公钥；无 proof、错 key/action/target/approval、过期、篡改或签名后修改请求
  均返回 `AUTHORIZATION_FAILED`；
- `TargetBootstrapExecutionRequest` 现在可携带与 target/approval 严格绑定的 authorization key pin，并以
  `expected_authorization_key_sha256` 区分首次安装与 CAS 轮换；目标只在 bootstrap credential 的固定
  `INSTALL_ACTIVATE` 入口接受该字段，STATUS/HEALTH/ROLLBACK 均拒绝；
- Bootstrap service 先验签 package、完成 preflight 并预检 pin CAS，再在 per-target transaction lock 下激活
  runtime，最后原子提交 pin。若进程在 runtime 激活后、pin 提交前中断，同一摘要绑定请求可根据已激活 manifest
  恢复并补交 pin，不重复安装；已提交 pin 可幂等返回 `ALREADY_CURRENT`，旧摘要轮换失败关闭；
- Adapter stage、activate/rollback、describe、project-evidence 和 source-discovery 的实际 target companion 入口默认启用该
  校验；release status 保持只读免授权。runtime forced credential 只扩大 `project-evidence`/`source-discovery` 固定只读入口，
  并同时要求 scoped proof；其余操作仍通过 bootstrap credential 的固定命令进入；
- 新增基于已验证 Event Record 的 SSE formatter；HTTP endpoint 和断线长轮询由 W7 接入。

W7 已进一步把 authorization pin 请求构造、独立审批、不可变 package ref 和实际 Bootstrap Job handler 串成
Controller 端公开 CLI/API 链，并交付默认只读文本 TUI 与 Local/discovery-only Adapt Job。target-side
project-evidence 与 bounded source-discovery 现已分别完成 public Job/Approval/proof/runner，并以摘要绑定进入 SSH Adapt Journey；
尚未完成的是四类 Adapter 请求的完整 Job 编排、目标侧运行时 discovery、远端进程终止确认、多主体 token/OIDC、
除 target runtime rollback 外的交互式 TUI 以及真实 sshd 矩阵。因此裸 `approval_id` 已不能获得目标权限，Bootstrap 软件事务与
Local 发现任务可运行，但当前仍不是可宣称完成的生产远程部署链。

### 0.9 W7 受控写、Target 注册与首个 Job handler

W7 已完成受控写链、secret-free Target 注册，以及第一个可实际推进状态机的只读连接评估 handler：

- 新增 `POST /v1/targets/{id}/bootstrap-jobs`、`POST /v1/targets/{id}/adapt-jobs`、
  `POST /v1/targets/{id}/project-evidence-jobs`、`POST /v1/targets/{id}/source-discovery-jobs`、
  `GET /v1/jobs/{id}`、JSON/SSE `GET /v1/jobs/{id}/events`、`POST /v1/jobs/{id}/run`、
  `POST /v1/jobs/{id}/cancel` 和
  `POST /v1/approvals/{id}/decisions`；
- 新增 `POST /v1/targets`、Target 列表/详情和 `POST /v1/targets/{id}/connection-assessments`；注册请求严格
  绑定 Local/SSH profile、connection/trust/host-key pin、principal 和 idempotency key，不连接目标、不保存凭据；
- 上述写接口即使绑定 loopback 也强制 `ROLO_API_TOKEN`、Bearer token、canonical
  `X-Rolo-Principal`、`X-Rolo-Permissions` 和 `Idempotency-Key`；token 必须由 Controller 配置绑定
  `ROLO_API_TOKEN_PRINCIPAL/PERMISSIONS`，请求头不能自报扩大身份或权限；target 与 approval 写权限分离；
- `DeploymentJobSubmission` 和 decision input 都是 `extra=forbid` 严格模型，不接受 shell/argv；API body
  继续受全局 Content-Length 与 size limit 保护；
- API 与 CLI 复用 `build_deployment_command`。interaction surface 不影响语义摘要，因此同 principal、
  idempotency key 和参数在 API/CLI 下生成相同 command digest；同 key 不同 payload 返回冲突；
- 新增 `robotctl target add`、`target connect assess`、`target package import`、`target bootstrap submit`、
  `target approval decide`、`target adapt submit`、`target job get/events/run/cancel`。Bootstrap submit 创建可运行的
  spec/Approval；Adapt submit 创建绑定注册摘要与本地 workspace 的可运行 discovery-only spec。任何 `CREATED`
  都不输出成部署或适配成功；
- `TargetDeploymentJobRunner` 已实现 `ASSESS_CONNECTION` handler：在 per-target lease 下验证提交时的注册摘要，
  对 `none/help/runtime-readonly` 执行 profile-only 或统一 Local/SSH typed inspection，原子持久化摘要绑定的
  `TargetConnectionAssessmentArtifact`，再推进 checkpoint/Job；Controller 在 artifact 写入、step 完成或 Job 完成
  任一窗口崩溃后都可幂等恢复，已完成探测不会重复执行；
- 注册 profile 发生漂移、inspection 失败或 runner 内部异常时均失败关闭；artifact 只保存有界错误码或已有的
  secret-closed inspection result，不持久化异常文本。取消在只读探测前或探测确认取消后进入确定终态；
- 新增 Controller `TargetBootstrapJobSpec/SpecStore/SubmissionService/JobRunner`：spec 绑定 Target registration、
  Controller package root、已验证 manifest、TargetProfile release-key pin、runtime CAS、authorization pin、
  独立 approver/expiry 和确定 approval ID；Command 的 `parameters_sha256` 必须等于完整 spec digest；
- Bootstrap submission 先原子创建 Job/spec/Approval，runner 再验证 APPROVED decision、command/target/action 和
  approval scope，随后在 Job per-target lease 与 remote checkpoint 下执行断点上传和 `INSTALL_ACTIVATE`；最终
  `TargetBootstrapJobArtifact` 与 checkpoint/final refs 摘要绑定。Controller 在 complete-step 后中断时重跑不会
  再次执行远端 Bootstrap；远端 transport 状态未知时进入 `BLOCKED/REQUIRES_RECONCILIATION`；
- package upload 与 Bootstrap operator 已全程透传 cancel token；取消发生在上传阶段时只留下可安全续传的 incoming
  chunks，取消发生在 SSH mutation 且终止结果未知时不宣称成功；
- Event JSON 分页和 SSE 都从已验证 hash-chain 读取；取消请求幂等；Approval decision ID 由 approval 与
  idempotency key 确定，同 key 同 decision 可安全重试，不同 decision 返回冲突；
- 新增公开 `TargetProjectEvidenceJob`：submission/spec/intent 冻结 registration、workspace、显式排序候选和独立
  R2 Approval；Runner 复核精确 unsigned request scope 后签发短时 proof，通过 Local 或 runtime SSH fixed command
  执行。目标只信任本地 authorization pin，只返回候选命中 metadata/digest，不接受 glob/递归扫描或文件内容；
  CLI/API/Session Agent/TUI 复用同一 Job 和审批语义，SSH 取消结果未知时进入 reconciliation；
- 新增公开 `TargetSourceDiscoveryJob`：独立 `ANALYZE_PROJECT_SOURCE` R2 Approval 冻结 registration、workspace、
  精确 scan roots、递归文件/字节/超时预算和完整 request digest；目标通过固定 forced command 校验本地 pin 与短时
  Ed25519 proof，拒绝绝对/父级/symlink 逃逸，只回传严格结构化依赖、入口点、ROS interface/name、语义候选、
  相对路径和摘要，不回传源代码、README/launch 正文、原始诊断或目标建议命令；
- 新增公开 `TargetRuntimeEvidenceJob`：独立 `COLLECT_RUNTIME_EVIDENCE` R2 Approval 冻结 registration、当前 collector
  descriptor/config/key pin、固定 `hw/linux/ros` layers、nonce、五分钟以内 issued/expires 和精确 unsigned request；
  Runner 仅在审批通过后签发短时 proof，通过 Local 或 runtime SSH fixed `evidence-v4` 命令采集，目标先验
  authorization pin，Controller 再验 collector Ed25519 bundle；
- `AdaptStartParameters/v2` 新增 `project_root_location=CONTROLLER|TARGET`。TARGET 路径只按目标绝对路径语法保存，
  不调用 Controller `Path.resolve()/exists()`；`TargetAdaptProjectEvidenceBinding` 冻结完成态 evidence Job、artifact、
  command、registration、workspace、manifest、observed paths 和 freshness。Adapt Runner 在 Journey 前重新加载并逐项
  复核，篡改、过期、目标混用或 registration 漂移均失败关闭；
- metadata-only、可选 structured-source 与 proof-bound runtime-readonly SSH Adapt 已接入 CLI/API/Session Agent/TUI
  canonical CLI。source binding 必须与 project-evidence 的 target/registration/workspace 一致；runtime-readonly 必须
  绑定完成态 runtime evidence Job。Runner 再验证
  artifact/request/summary digest 与 freshness；Journey 使用独立 `TARGET_SOURCE` 低置信度层级，并明确保持所有
  Controller source/build/install roots 为空；运行时 bundle 在提交与执行阶段都按当前 pin 重新验签，Journey 只消费
  preverified ProbeResult，不会再发未审批的临时探测；
- W7 API/CLI/Job Store 联合测试与既有只读 API 兼容测试通过，W7 模型已进入 canonical Schema export。

W7 公开 Bootstrap slice 现已完成：

- 新增 Controller `TargetPackageRegistry`。只有本地 CLI import 接受显式源目录；包先按当前 TargetProfile 的
  release Ed25519 pin 校验严格文件集，再复制到同文件系统 staging、复验并原子发布为
  `<package_id>@<manifest_sha256>`。并发重复导入幂等，stored tamper、pin 漂移、路径逃逸、symlink、额外/缺失文件
  和 metadata/package size 越界均失败关闭；registry record 不保存源路径；
- `POST /v1/targets/{id}/bootstrap-jobs` 与 CLI submit 只接受 package ref，不接受 Controller filesystem path。
  首次请求持久化 submission intent，冻结 approval expiry、authorization pin 时间和完整 spec；同一
  target/idempotency key 可跨 CLI/API 重试，同 key 不同请求摘要冲突；
- `target add` 可原子配置 release signing key ID/path/digest；Controller authorization key ID/path 也必须成对配置。
  Bootstrap 默认为 `expect_current_present=false`，升级必须显式提供 present/CAS digest；
- `target approval decide` 补齐 CLI 审批路径，请求人不能自批。Job runner 在审批通过后执行签名上传、目标端二次验签、
  runtime 激活和 authorization pin 提交；artifact 还会反向校验 target/package/manifest/release-key/pin digest 与 spec；
- API/CLI/registry 集成测试覆盖 arbitrary package path 拒绝、并发 import、stored tamper、当前 pin 复验、冻结时间幂等、
  requester/approver 分离以及公开审批流程。
- 新增只读 `target tui` 文本工作台和 `TargetDeploymentTuiSnapshot`：Fleet、Target、Job、Approval、
  Blocker/Recovery 页面复用同一持久 Store，显示相同 state/recovery 语义与 canonical CLI；`--watch` 只刷新 snapshot，
  不创建或重试 Job。审批仍由显式 CLI/API 决策，TUI 不持有 SSH 私钥或自由终端能力。
- 新增 `TargetAdaptJobSpec/SpecStore/SubmissionService/JobRunner`：CLI/API 从已注册 Local Target 派生 workspace，
  冻结 `AdaptStartParameters` 和 registration digest，以相同 idempotency key 得到相同 command digest；Journey result
  先独立持久化，再写摘要绑定的 final artifact，两个崩溃窗口均可恢复而不重复执行；已知 Journey blocker 进入
  `BLOCKED/NONE`，执行开始但无结果时重启进入 `REQUIRES_RECONCILIATION`。
- 当前 Adapt slice 接受 `LOCAL + run_adapter_agent=false`，以及绑定新鲜 project-evidence artifact、可选再绑定
  source-discovery artifact 的 `SSH + active_probe=none + run_adapter_agent=false` Journey；也接受额外绑定新鲜、已
  重新验签 runtime-evidence artifact 的 `SSH + active_probe=runtime-readonly` Journey。后者不读取文件正文；source
  slice 只消费 proof-bound 结构化源码事实，运行时 slice 只消费 proof-bound `hw/linux/ros` 结果。自动 Agent/release
  请求等待 release-scoped
  Approval 链，不能借 discovery Job 越权启用。
- `TargetProfile` 的 Local workspace 现在接受当前宿主机的原生绝对路径（Windows 盘符会规范化为 `/`）；SSH
  workspace 继续只接受目标侧绝对 POSIX 路径，Controller 不对该路径调用本机文件系统 API。

W7 尚未完成自动 Agent/release 审批与写链、多主体 token registry/OIDC、真实 sshd 下的
远端 cancel confirmation、除 target runtime rollback 外的交互式 TUI 控件/长轮询 SSE 和主机账号/systemd
安装体验，状态保持软件核心进行中。

## 1. 产品目标

用户可以通过以下任一入口完成等价任务：

```bash
rolo target add wheeltec --ssh robot@192.168.1.20
rolo adapt start --target wheeltec --workspace /home/robot/wheeltec_ws
```

```text
通过 SSH 连接 192.168.1.20，把它注册为 wheeltec，
然后发现 /home/robot/wheeltec_ws 并执行只读适配。
```

GUI/TUI 应提供相同的目标选择、连接检查、风险提示、审批、进度、阻塞原因和制品下钻。
所有入口必须产生相同的 Run、Event、Evidence、Gate 和 Audit 记录。

### 1.1 成功标准

- 首次接触一台满足前置条件的 Linux 目标机时，用户不需要手工输入 Collector 命令；
- Local 和 SSH 两种 Target Executor 通过同一套 conformance contract；
- SSH bootstrap 可幂等重试，失败不会留下被误认为已注册的半成品；
- GUI/TUI/CLI/Natural Language 创建的等价任务产生相同规范化 Command；
- Agent 可以动态检查和修正路径，不需要预先冻结所有步骤；
- 任何安装、sudo、主机密钥首次接受、身份替换和升级都进入审批与审计；
- SSH credential、Collector 私钥和 API token 不进入 Agent prompt、artifact 或普通日志；
- 目标证据继续绑定 robot、collector、target、nonce、freshness 和 payload digest；
- SSH 模式的 CLI/virtualenv/editable source 路径在目标侧按 PR #17 Runtime Context 和 sandbox
  规则验证，控制器不伪造本地等价路径；
- 远程 Gate 只使用绑定 release digest 的目标侧 `describe` attestation，不执行 `invoke`；
- 完整 Adapt 仍必须通过现有独立 Gate 才能发布 release。

### 1.2 非目标

首个 MVP 不实现：

- 自由远程终端或浏览器内 Shell；
- 远程 IDE、断点调试、任意进程注入；
- 无人批准的任意 root 命令；
- Windows、FreeRTOS、CyberRT 目标端 Provider；
- 多租户 SaaS 控制面；
- 让 Adapter Agent 直接部署或更新目标机；
- 用自然语言文本替代 Operation Contract、Policy、Gate 或 Audit；
- 用 SSH 成功连接冒充真机行为、安全或可靠性验收。

## 2. 统一产品模型

现有 `EvidenceDeploymentMode.LOCAL/REMOTE` 只描述证据传输，不足以表达新产品。新增三个正交
维度：

| 维度 | 首版取值 |
|---|---|
| Orchestrator placement | `TARGET_LOCAL`、`CONTROLLER` |
| Target transport | `LOCAL`、`SSH` |
| Interaction surface | `CLI`、`TUI`、`GUI`、`NATURAL_LANGUAGE` |

典型组合：

| 场景 | Orchestrator | Transport | 说明 |
|---|---|---|---|
| 目标机直接运行 Rolo | `TARGET_LOCAL` | `LOCAL` | 当前默认路径的产品化 |
| 控制器远程适配 | `CONTROLLER` | `SSH` | 控制器运行 Agent/Gate，目标机运行最小 companion |
| GUI 管理目标机本地 Rolo | `TARGET_LOCAL` | `SSH` bootstrap + API | SSH 用于安装/隧道，业务由目标 API 承载 |
| GUI 管理控制器 Rolo | `CONTROLLER` | `SSH` | GUI 连接控制器，控制器管理目标 |

不得再用一个 `remote=true` 同时推断运行位置、证据来源、凭据位置和 release 部署位置。

## 3. 总体架构

```text
CLI / TUI / GUI / Natural Language
                 |
                 v
       Application Command Bus
                 |
       Policy / Approval / Audit
                 |
                 v
       Resumable Deployment Job
         |                 |
         v                 v
 LocalTargetExecutor   SshTargetExecutor
         |                 |
         +--------+--------+
                  v
          target-side rolo-target
        bootstrap / enroll / probe
                  |
          signed target evidence
                  v
          existing AdaptJourney
                  |
       Adapter Agent -> freeze bundle
                  |
                  v
       target sandbox `describe` attestation
                  |
                  v
       Gate -> immutable release + target deployment
```

在 `CONTROLLER + SSH` 模式中，控制器不得尝试挂载或执行目标机的绝对 CLI/virtualenv 路径。
目标端 companion 接收按 digest 冻结的 Bundle，在 PR #17 已建立的 production sandbox 中执行
`describe`，返回绑定 target、release、runtime-context 和输出 digest 的结构化结果。独立 Gate
验证该结果后才允许发布。正式 `invoke` 仍只能由授权 Runtime 在目标侧发起。

### 3.1 单一 Agent，分级工具权限

用户只感知一个 `RoloSessionAgent`。内部提供结构化工具：

```text
target.connection.inspect       READ_ONLY
target.hostkey.approve          APPROVAL_REQUIRED
target.bootstrap.plan           READ_ONLY
target.bootstrap.execute        HOST_MUTATION
target.enroll                   IDENTITY_MUTATION
target.evidence.collect         READ_ONLY
adapt.start                     LONG_RUNNING_JOB
target.upgrade                  HOST_MUTATION
target.enrollment.rotate        IDENTITY_MUTATION
target.release.stage            HOST_MUTATION
target.release.describe         TARGET_READ_ONLY_EXECUTION
target.release.activate         HOST_MUTATION
```

同一 Agent 可以依次调用这些工具，但工具运行时负责：

- 参数和 Schema 校验；
- 获取 credential reference 对应的秘密；
- 权限与审批检查；
- SSH/本地命令执行；
- 输出限额和脱敏；
- 状态落盘、幂等、取消和审计。

Agent 只能看到 credential reference，不读取私钥正文。

### 3.2 自然语言边界

自然语言可以动态调用工具，不要求每次生成完整 JSON Plan。以下内容仍必须结构化：

- target identity 与 connection profile；
- workspace 和 Rolo version；
- 目标动作、风险和所需权限；
- host-key decision；
- approval decision；
- job/step/event 状态；
- artifact、digest、enrollment 和 release 身份；
- retry、cancel、rollback 和 rotation。

系统必须始终可以从一次自然语言任务导出等价 canonical CLI，用于复现和审计。

## 4. 信任与安全模型

### 4.1 两阶段 SSH 身份

首次 bootstrap 使用部署身份，可拥有经过批准的安装权限；部署完成后使用目标最小权限身份：

```text
bootstrap credential
  -> platform inspection
  -> signed package installation
  -> account/service creation
  -> enrollment
  -> bootstrap credential no longer used by ordinary Adapt

runtime credential
  -> fixed or typed rolo-target protocol
  -> no PTY
  -> no port/agent/X11 forwarding by default
  -> no sudo
```

bootstrap credential 不能进入 Adapter Agent workspace 或 prompt。

### 4.2 SSH 主机信任等级

首版定义：

| 等级 | 规则 | 默认用途 |
|---|---|---|
| `STRICT` | 预置 host key 或企业 SSH CA | 生产默认 |
| `CONFIRMED` | GUI/TUI 展示指纹并由用户明确确认 | 首次实验室接入 |
| `TOFU_DEV` | 首次记录，明确标注低保证 | 本地开发，默认关闭 |

任何等级变化都生成 transition audit。主机密钥变化不能静默接受。

### 4.3 Collector 签名迁移

当前 v2 使用 HMAC shared secret，远程模式要求控制器持有 verification secret。产品化自主部署
应新增 `robot-target-evidence-collector/v4`：

- 目标机生成 Ed25519 key pair；
- 私钥保持目标本地 `0600`，可选 TPM-backed provider；
- descriptor 携带 public key、key ID 和算法；
- bundle 使用 detached Ed25519 signature；
- rotation transition 由旧 key 签名，新 key 重新固定；
- 控制器不再复制 Collector 签名秘密。

迁移期继续只读支持 v1-v3 HMAC bundle；新自主 bootstrap 默认生成 v4。旧协议不能被静默升级或
冒充 v4。

### 4.4 Agent 与执行器边界

- 会话 Agent 可以决定下一项工具调用；
- 执行器只执行已注册工具，不执行模型拼接的隐藏 shell 字符串；
- 专家模式可以提供显式 raw SSH escape hatch，但默认关闭、逐次审批并完整审计；
- 高风险参数必须在执行前向用户显示规范化摘要；
- Agent 不得批准自己的权限提升；
- Adapter Agent 只能访问现有 bounded inspection surface。

## 5. 新增领域契约

建议新增以下版本化 Schema：

```text
schemas/TargetProfile.schema.json
schemas/TargetConnectionProfile.schema.json
schemas/TargetConnectionAssessment.schema.json
schemas/BootstrapPlan.schema.json
schemas/DeploymentCommand.schema.json
schemas/DeploymentJob.schema.json
schemas/DeploymentStep.schema.json
schemas/DeploymentEvent.schema.json
schemas/ApprovalRequest.schema.json
schemas/TargetEnrollmentV4.schema.json
schemas/TargetRuntimeStatus.schema.json
schemas/LocatedRuntimeContext.schema.json
schemas/RemoteReleaseDeployment.schema.json
schemas/TargetDescribeAttestation.schema.json
```

### 5.1 TargetProfile 最小字段

```json
{
  "schema_version": "rolo-target-profile/v1",
  "target_id": "wheeltec",
  "orchestrator_placement": "CONTROLLER",
  "transport": "SSH",
  "connection_profile_id": "conn-wheeltec-lab",
  "workspace_root": "/home/robot/wheeltec_ws",
  "desired_rolo_version": "v0.2.0",
  "trust_level": "STRICT"
}
```

不得写入 SSH private key、password、token 或 Collector private key。

`LocatedRuntimeContext` 必须区分 `TARGET` 与 `CONTROLLER` 路径。目标路径由目标端 companion
验证存在性、类型、digest 和 Operation 作用域；控制器只验证 Schema、来源和签名，不调用本机
文件系统验证目标路径。PR #17 已定义的 `PATH`、`PYTHONPATH`、ROS/DDS 环境字段继续复用，
不得引入第二套不兼容 Runtime Context。

### 5.2 DeploymentCommand

所有交互入口规范化为命令，例如：

```json
{
  "schema_version": "rolo-deployment-command/v1",
  "command": "BOOTSTRAP_AND_ADAPT",
  "target_id": "wheeltec",
  "workspace_root": "/home/robot/wheeltec_ws",
  "active_probe": "runtime-readonly",
  "run_adapter_agent": true,
  "requested_by": "session-agent",
  "interaction_surface": "NATURAL_LANGUAGE"
}
```

`requested_by` 不是授权；执行时仍需要主体身份、policy 和 approval evidence。

### 5.3 Job 与 Event

Job 状态：

```text
CREATED
CONNECTING
HOST_KEY_APPROVAL_REQUIRED
PREFLIGHT
BOOTSTRAPPING
ENROLLING
COLLECTING_EVIDENCE
DISCOVERING
ADAPTING
GATING
COMPLETE
BLOCKED
FAILED
CANCELLED
```

每个 Event 至少绑定：

```text
job_id
step_id
target_id
event_type
timestamp
attempt
status
sanitized_summary
artifact_refs
approval_ref
```

## 6. 代码组织建议

新增：

```text
src/rolo/targets/
├── models.py
├── profiles.py
├── credentials.py
├── trust.py
├── executor.py
├── local.py
├── ssh.py
├── bootstrap.py
├── enrollment.py
├── packaging.py
├── release_deployment.py
├── describe_attestation.py
└── conformance.py

src/rolo/jobs/
├── models.py
├── store.py
├── events.py
├── runner.py
├── approvals.py
└── recovery.py

src/rolo/application/
├── commands.py
├── command_bus.py
├── target_service.py
└── adapt_service.py

src/rolo/api_routes/
├── targets.py
├── jobs.py
├── approvals.py
└── events.py
```

修改：

- `commands/lifecycle.py`：从直接编排迁移为 Application Command client；
- `commands/target_evidence.py`：保留兼容入口，接入 v4 enrollment；
- `stages/adapt/target_evidence.py`：增加非对称签名和 transport-neutral verifier；
- `stages/adapt/journey.py`：拆出 checkpoint/event hook，不改变 Gate 权威；
- `runtime_context.py`：在现有 PR #17 字段上增加 location/provenance，不另建环境白名单；
- `stages/adapt/target_fingerprint.py`：目标路径存在性改由目标端验证并绑定 attestation；
- `adapter_runner.py` 与 `scripts/rolo-adapter-sandbox`：保留同一沙箱 ABI，增加 target companion
  调用和 conformance，不复制实现；
- `adapter_runtime.py` 与 `stages/adapt/conformance.py`：接入目标侧 `describe` attestation，继续禁止
  Promotion `invoke`；
- `core/config.py`：增加非秘密 connection/profile 配置；
- `api.py`：保留 read models，将写路由拆到独立 router；
- `runtime.py`：注入 Command Bus、Job Store、Credential Provider；
- `schema_export.py`：导出新 Schema；
- `docs/TARGET_DEVICE_OPERATION_MANUAL_ZH.md`：增加 Agent-assisted flow，保留手工严格流程。

GUI 工作预计主要发生在配套 `rolo-vis` 仓库，本仓库负责稳定 API、SSE、Schema 和 read model。

## 7. 实施工作包

### W0：ADR、威胁模型与产品契约

状态：`COMPLETED`

目标：冻结术语、信任根、运行位置和首版范围，避免 UI 与 transport 先行后返工。

交付物：

- Orchestrator/Transport/Interaction 三维 ADR；
- 单一 Agent、多工具权限 ADR；
- SSH bootstrap threat model；
- HMAC v2/v3 到 Ed25519 v4 迁移 ADR；
- PR #17 Runtime Context/Sandbox 复用 ADR；
- Controller Gate 与 target-side `describe` attestation ADR；
- 新 Schema 初稿；
- Linux x86_64/ARM64 支持矩阵；
- `rolo-target` 是一次性入口还是常驻服务的决定。

验收：

- 明确 bootstrap credential 和 runtime credential 生命周期；
- 明确首次 host-key trust UX；
- 明确哪些动作自动执行、哪些必须审批；
- 明确 release 的控制器权威副本、目标部署副本和目标侧运行位置；
- 明确控制器不得验证或挂载目标绝对路径。

估算：`1-2 人周`

### W1：Application Command Bus 与 TargetProfile

状态：`COMPLETED`

依赖：W0

目标：让 CLI、API 和未来 UI 使用同一业务入口。

交付物：

- `TargetProfile`、`ConnectionProfile` 和无秘密持久化；
- credential reference SPI；
- `DeploymentCommand` validator；
- in-process Command Bus；
- 当前 `adapt start` 通过 Command Bus 调用的兼容路径；
- canonical CLI renderer。

验收：

- 当前本地 `adapt start` 行为和输出保持兼容；
- CLI 与直接 service 调用生成同一 Command digest；
- profile/artifact 不包含秘密；
- 未知字段和非法路径失败关闭。

估算：`3-4 人周`

### W2：LocalTargetExecutor 与 SshTargetExecutor

状态：`COMPLETED`

依赖：W0、W1

目标：统一目标检查和命令执行，不把 raw SSH 暴露给业务层。

交付物：

- `TargetExecutor` protocol；
- local/ssh 双实现；
- SSH config、Port、Identity、ProxyJump 和 known_hosts 支持；
- bounded stdin/stdout/stderr、timeout、cancel 和 process cleanup；
- read-only inspection tools；
- Target Executor conformance kit。

验收：

- Local 与 SSH 对同一 inspection contract 返回一致模型；
- `BatchMode` 和 strict host-key policy 不可被 Agent 参数关闭；
- command arguments 不经过 shell 拼接；
- 网络中断、超时、非零退出和超限输出具有确定错误码；
- SSH secret 不进入日志。

估算：`3-4 人周`

### W3：目标端制品与幂等 Bootstrap

状态：`IN_PROGRESS`

依赖：W2

目标：替换正式产品对 `git clone + uv sync` 的依赖。

交付物：

- x86_64/ARM64 可校验目标端制品；
- release manifest 与签名/digest；
- platform/preflight detector；
- bubblewrap、user/mount/network namespace 自检；
- PR #17 `PATH`/`PYTHONPATH`/virtualenv runtime capability 自检；
- address-space 与 process/thread budget 评估；
- upload、verify、install、activate、health-check、rollback；
- 最小权限账号和 systemd/forced-command 模板；
- bootstrap dry-run 与 approval summary；
- idempotent install state。

验收：

- 相同版本重复 bootstrap 不产生额外身份；
- 上传中断不会激活不完整版本；
- health check 失败自动恢复旧版本或保持未激活；
- 离线目标可以从控制器上传制品安装；
- sudo 动作逐项列入审批摘要；
- LeRobot 等 ML-backed CLI 所需预算不足时在 Adapt 前返回结构化 blocker。

估算：`4-6 人周`

当前软件核查补充：`TargetConnectionProfile` 已新增显式的 provisioning、bootstrap 与 runtime 三阶段
SSH 身份引用；executor 会按 `CredentialPurpose` 只解析对应用户/密钥，缺少 provisioning 身份时失败关闭，
且 registration digest 会绑定全部身份引用。现有 package transaction 安装在执行 bootstrap credential 的用户状态目录，而
`TargetHostTemplateBundle` 的 systemd/forced-command 默认运行 `rolo` 账号下的固定
`/opt/rolo/bin/robotctl`。在公开主机安装事务前，必须先冻结 bootstrap 管理连接与 runtime 最小权限连接的
身份切换，以及固定 launcher 如何解析已激活的 digest-bound runtime；不能用同一身份引用隐式代表三套
权限，也不能只把模板写进 `/etc` 就宣称 W3 完成。该缺口保持 `IN_PROGRESS`，并列入 W3
后续契约与真实 Linux 验收。

当前新增 `TargetHostTemplateBundle/v2`、固定 bootstrap dispatcher、manifest-verifying runtime launcher、
`TargetHostProvisioningPlan/v1`/Step Schema 和只读 `robotctl target host plan`。计划把最小账号、目录、两把
forced-command 公钥、dispatcher、launcher、systemd unit、daemon-reload 与 enable 的路径、权限、argv 和
digest 全部列入 `USE_SUDO` 范围，并故意不在 runtime 尚未激活时 `--now`。SSH bootstrap 传输/安装已改用
三条稳定 original-command 标签，不再把动态 base64 Python 命令放进 authorized-key 命令面。持久
`PROVISION_HOST` Job 已冻结 exact plan、R3 `USE_SUDO` Approval、目标 registration、CAS 与 artifact；固定
root installer 只从 stdin 读取计划并拒绝形状/digest/路径/step/sudo-scope 漂移，远端结果未知时进入
`REQUIRES_RECONCILIATION`。现已新增 R2 特权只读 observer 和 `RECONCILE_HOST` Job：EXACT、
NOT_COMMITTED、DIFFERENT_CURRENT、DRIFTED、FAILED 结果均严格绑定冻结计划，且只有 EXACT 能把原作业闭合为
成功。host rollback 与激活后 service start/reconcile 已具备持久 intent/spec/Approval/Job/CLI/API 和 CAS/
digest-bound 执行入口；尚缺真实 root/systemd/sshd 证据，因此 W3 状态不变。

### W4：Enrollment v4 与 Collector 自动初始化

状态：`SOFTWARE_CORE_COMPLETE_HOST_VALIDATION_PENDING`

依赖：W0、W2、W3

目标：目标本地生成身份与私钥，用户无需手工运行 `collector-init`。

交付物：

- Ed25519 Collector descriptor/bundle；
- target-local key generation；
- controller public-key pin；
- challenge/nonce/freshness 验证；
- v4 rotation transition；
- v1-v3 只读兼容；
- `target.enroll` 工具；
- target-side workspace/ROS/help executable 自动发现与 digest pin；
- 现有 `collector-init` 兼容 wrapper。

验收：

- private signing key 从不离开目标；
- descriptor 或 bundle 篡改失败关闭；
- replay、过期、robot/collector/host mismatch 被拒绝；
- 并发 enrollment 只有一个成功；
- 断电/中断不会产生可被误用的半注册身份；
- 本地与 SSH 自动 enrollment 使用同一状态机。

当前实现进度：`CollectorConfigurationDiscoveryV4` 只携带注册 workspace root、有限且排序的相对 help
executable 候选和 ROS 自动选择开关。目标侧拒绝 traversal、symlink、越界、非普通文件和超限文件，随后
计算 digest、稳定 executable ID，并按既有 ROS 选择策略固定 `/opt/ros` 与 workspace overlay。
`robotctl target enroll --auto-configuration` 将解析出的完整 configuration 纳入 descriptor、attestation、
Controller pin 和 rotation transition；显式 `--configuration-json` 只作为专家/恢复兼容入口。legacy
`target-evidence collector-init` 继续只读兼容，不是新部署的前置步骤。剩余门禁是 W3 主机身份切换与 W10
真实 x86_64/ARM64、sshd、中断和权限矩阵。

估算：`3-5 人周`

### W5：位置感知 Runtime Context、目标侧 Sandbox 与 Release 部署

状态：`SOFTWARE_CORE_COMPLETE_HOST_VALIDATION_PENDING`

依赖：W2、W3、W4

目标：控制器负责编排、Agent 和独立 Gate，所有目标绑定 CLI/virtualenv 路径的验证、`describe`
及授权后 `invoke` 在目标机 PR #17 production sandbox 中执行。

交付物：

- `TargetWorkspaceRef`；
- 目标端有界源码/制品 manifest；
- 签名摘要和选择性 artifact transfer；
- remote project evidence detection；
- `LocatedRuntimeContext`，复用 PR #17 的 Operation-scoped `PATH`、显式 `PYTHONPATH` 和资源预算；
- frozen Bundle 分阶段上传、digest 校验和目标端只读 staging；
- 目标侧 `describe` 执行协议；
- `TargetDescribeAttestation`，绑定 robot、collector、target、release、Bundle、Runtime Context、
  sandbox launcher 和 describe output digest；
- Controller Gate 对 attestation、Bundle mapping 和 freshness 的验证；
- Gate 通过后的 target release activation/rollback；
- `AdaptJourney` transport-neutral target probes；
- controller/target artifact provenance；
- 目标端 runtime/current index 与控制器权威 release index 的一致性协议。

验收：

- 控制器不把自己的 build/install 冒充目标制品；
- 控制器不对目标绝对 PATH/PYTHONPATH 执行本机 `Path.exists()`；
- 目标路径越界、symlink escape 和超限传输被拒绝；
- 同一 workspace snapshot 可重复得到相同 manifest digest；
- target `describe` 只运行选中 Bundle Operation 所需的 CLI/virtualenv 路径；
- target `describe` 使用与 PR #17 Local 模式相同的 sandbox conformance fixture；
- Promotion 和部署冒烟测试都不执行 `invoke`；
- attestation、runtime context、release 或 sandbox digest 不匹配时 Gate 失败；
- activation 中断不会替换现有 target current release；
- target evidence 失败不回退控制器探针；
- 现有 Local Journey 回归不变。

估算：`6-9 人周`

### W6：Job、Event、Approval 与恢复

状态：`IN_PROGRESS_SOFTWARE_CORE`

依赖：W1；与 W2-W5 并行演进

目标：支撑长任务、GUI/TUI、断线重连和自然语言动态执行。

交付物：

- atomic Job Store；
- append-only sanitized Event log；
- step checkpoint；
- per-target lock；
- cancel/retry/resume；
- approval request/decision；
- approval-scoped、target-verifiable Ed25519 authorization proof 与 target-local key pin；
- restart recovery；
- SSE stream。

验收：

- 服务重启后可恢复或明确终止未完成 Job；
- 同一目标不能并发执行冲突部署；
- approval 绑定 command digest、principal、expiry 和精确 request scope；
- 目标拒绝裸 approval、请求自带公钥、错 action/target/payload、过期或篡改的 capability；
- 取消后远端进程被终止或标为需要人工确认；
- Event 不泄漏 secret 或任意文件内容；
- Job 完成状态与最终 artifact 一致。

估算：`4-6 人周`

### W7：受控写 API、CLI 与 TUI

状态：`IN_PROGRESS_SOFTWARE_CORE`

依赖：W1、W6；SSH 完整体验依赖 W2-W5

交付物：

```text
POST /v1/targets
POST /v1/targets/{id}/connection-assessments
POST /v1/targets/{id}/bootstrap-jobs
POST /v1/targets/{id}/adapt-jobs
GET  /v1/jobs/{id}
GET  /v1/jobs/{id}/events
POST /v1/jobs/{id}/run
POST /v1/jobs/{id}/cancel
POST /v1/approvals/{id}/decisions
```

同时交付：

- CLI target/connect/bootstrap/adapt 命令；
- 兼容现有 `robotctl adapt start`；
- TUI Fleet/Target/Job/Approval/Blocker 页面；
- canonical CLI 显示；
- API token、body limit、idempotency key 和审计。

验收：

- CLI、TUI 和 API 创建相同命令时 Command digest 一致；
- 所有 mutating API 需要身份、权限和 idempotency key；
- TUI 断线重连不重复创建 Job；
- API 不接受自由 shell；
- 当前 read-only API 兼容。

估算：`4-7 人周`，其中 TUI `2-4 人周`

### W8：GUI Workbench 部署体验

状态：`COMPLETED_RUNTIME_EVIDENCE_CONTROL_SCOPE（独立 authenticated control 插件与 proof-bound SSH runtime discovery 已完成；完整 SSH release 体验受 W9/W10 约束）`

依赖：W6、W7

目标：在现有只读 rolo-vis 工作台上增加目标接入与任务控制，不引入自由终端。

页面：

- Add Target；
- SSH fingerprint confirmation；
- Connection Assessment；
- Bootstrap Plan 与权限摘要；
- Live Job Timeline；
- Approval Drawer；
- Blocker/Recovery；
- Adapt result、Gate、Evidence 和 canonical CLI。

验收：

- GUI 不持有 SSH private key；
- 刷新页面后恢复当前 Job；
- 高风险审批显示目标、动作、版本、路径和 digest；
- GUI 与 TUI 显示相同状态语义；
- 无 SECRET payload 进入浏览器响应。

估算：`5-8 人周`；若不能复用现有 rolo-vis，再增加 `6-10 人周`

当前实现进度：

- rolo producer 新增 `GET /v1/deployment-workbench` 与
  `TargetDeploymentWorkbenchSnapshot/v1`，直接投影 W7 的 Target/Job/Approval/Recovery Store；GUI 与 TUI
  因而共享状态、blocker、recovery 和 canonical CLI 语义，没有第二套前端状态机；
- Target 页只暴露 host/port/user/SSH fingerprint 等非 secret 信任摘要，不暴露 credential ref、known_hosts
  Controller 路径或私钥；Approval 页显示 target、action、risk、desired version、workspace、command/scope digest，
  Bootstrap 时附 package ref/manifest digest，但不暴露 Controller package root 或发布公钥正文；
- 配套 `rolo-vis` 已新增 feature-negotiated Deployment 页面、严格字段 allowlist、secret-bearing response 拒绝、
  Target 列表、目标摘要、持久 Job timeline 与 canonical CLI；复用已冻结的深色、证据导向视觉系统；
- `rolo-vis` 当前 durable MVP policy 与 plugin manifest 仍为 read-only，因此 Add Target 与其他写控件保持禁用，
  没有把 API token、SSH 凭据或任意命令输入引入浏览器；类型检查、208 项前端测试、生产构建和 Sites worker
  验证通过。

产品决策已冻结为第二种方案：现有 `rolo-vis` 的 manifest、入口和客户端继续保持 read-only；同一仓库新增独立
`rolo-deployment-control` 插件和生产构建产物。新插件先调用无副作用的 `GET /v1/deployment-session`，验证
Bearer token 与 Controller 侧 principal/permissions 绑定；token 只存在当前 React 内存，不进入 URL、
LocalStorage、SessionStorage、日志、fixture 或构建产物，disconnect/reload 后失效。

authenticated control 插件已接入 Add Target、独立信道 fingerprint 确认、connection assessment、
discovery-only Adapt submit、Bootstrap submit、Job run/cancel、5 秒持久状态刷新、Approval drawer、
Blocker/Recovery 和 canonical CLI。每个写请求只声明该路由所需的 `target:write` 或 `approval:write`，并使用新的
canonical idempotency key；Approval 控件还要求当前 session principal 等于被冻结的 approver。插件不接受 SSH
私钥、自由 shell/argv 或任意文件浏览。

插件的 Target evidence chain 现已接入 project-evidence/source-discovery/runtime-evidence 三个独立 R2 Approval
提交入口。前两份完成态 Job 可绑定 `active_probe=none` Adapt；额外绑定最长 300 秒的新鲜 runtime Job 时提交
`active_probe=runtime-readonly`。GUI 首版把 source scan root 固定为 `.`、runtime layers 固定为 `hw/linux/ros`，
不暴露任意路径、正文或命令输入；Approval 决策和 Job run 仍是显式独立步骤。相关 TypeScript 检查、控制面契约
测试与 production build 通过。

为维持浏览器响应的 secret-closed 边界，Bootstrap HTTP response 已从内部
`TargetBootstrapJobSubmissionResult` 改为公开 `TargetBootstrapApiSubmissionResult/v1`，只返回 Job、Approval、
package ref 和 manifest digest；Controller `package_root`、发布公钥正文和 authorization pin 只保存在内部 spec。
当前 Controller 认证配置仍是单个 `ROLO_API_TOKEN` 绑定单 principal；多主体并发登录/OIDC 属于后续生产认证
硬化，不允许通过客户端自报 principal 绕过。runtime evidence 软件闭环已进入 W8；release Gate/activate 结果和
真机 SSE/断线体验仍由 W9/W10 的后端能力决定，不由 GUI 伪造状态。

### W9：自然语言 Session Agent

状态：`IN_PROGRESS_BROKER_SLICE（无显式意图计划；authenticated broker、Codex 单步编排、CLI/API/GUI 已接入）`

依赖：W1、W6、W7；可在 CLI/TUI 稳定后开始

目标：一个 Agent 动态调用目标、部署和 Adapt 工具。

交付物：

- bounded tool catalog；
- conversation-to-command adapter；
- missing-input clarification；
- tool result summarization；
- approval handoff；
- canonical CLI reproduction；
- prompt-injection and untrusted target-output isolation；
- Agent action budget、timeout 和 cancel。

验收：

- Agent 不读取 credential material；
- 目标机 banner、README、日志不能改变工具 policy；
- Agent 不能批准自己的 host mutation；
- 等价自然语言与 CLI 产生等价 Command；
- 模型失败不会跳过 Gate 或把 Job 标为成功；
- 不确定目标、路径或权限时请求澄清，不猜测执行。

估算：`3-5 人周`

#### 首版无显式意图方案评估（2026-08-26）

首版可以不要求模型先输出单独的“意图 JSON”，由接入的 Codex 根据对话自主选择命令；但不能因此把
Controller shell、原始 `robotctl`、SSH 凭据、Target 网络或 Approval 决策权直接交给模型。自然语言不必先
结构化成显式意图，权限、参数、身份和副作用边界仍必须由确定性组件结构化并强制执行。

直接让 Codex 以 Controller OS 身份执行任意 `robotctl`/shell 的方案不进入生产实现，主要风险为：

- CLI 当前不是 HTTP authenticated principal boundary；若允许模型填写 approver/principal，会产生身份冒用和
  自批准风险；
- 可写 Controller 配置、Job/Approval store 或 Python import path 时，模型可绕过命令、Gate 和审计语义，直接
  篡改持久状态；
- 暴露 API token、SSH key、credential ref 的解析能力或不受限网络后，目标端脚本、banner、README 和日志可
  形成 prompt injection 或凭据外泄通道；
- 自由 shell 的组合、重定向、路径遍历和重试行为无法稳定映射 idempotency、Command digest、timeout、cancel
  与恢复语义；
- Codex sandbox 只能约束文件、进程和网络访问，不能代替 Rolo 的 Target allowlist、Approval 分权、release
  Gate 和 Evidence policy；
- 非交互命令的工具级 approval 与 Rolo 的持久化领域 Approval 不是同一机制，不能相互替代。

推荐首版采用“自主选择 + 认证 broker 执行”：Codex 在隔离、临时、低权限环境中运行，只能调用专用
`rolo-agentctl`（名称暂定）的有限命令语法；独立于模型进程的 broker 绑定 session principal，校验 target
allowlist、action budget、timeout、cancel、idempotency 和每个动作所需 permission，然后调用 W7 的领域服务。
Codex 不能访问源代码、Controller store、credential material、通用网络或原始 SSH，也不能决定 Approval；
mutating command 仍创建冻结的 Job/Approval，并仅在独立主体持久批准后运行。broker 只向模型返回 allowlist
过滤后的结构化 receipt，目标端原始输出不重新进入模型上下文；canonical CLI 继续用于人工复现和审计。

这一方案保留了用户希望的自主体验，也允许后续根据失败样本再引入显式 intent schema，而不把模型输出本身当作
授权边界。工程估算为：不安全的直连演示约 `0.5-1 人周`（拒绝产品化）；brokered autonomous CLI 首个可验收
切片约 `2-4 人周`；prompt-injection eval、重试/恢复和真实 SSH 生产硬化再需 `2-4 人周`，后半部分与 W10
重叠。现有严格意图 Session Agent 代码仅保留为未集成原型，在方案冻结前不计入 W9 完成度。

当前实现已按推荐方案建立第二版契约：`agent_broker.py` 每次只接受一个严格命令，principal、permission、
sequence 和 idempotency 均由 Controller 会话绑定，命令模型没有 shell、argv、credential、requested-by 或
Approval decision 字段。目标 allowlist、action budget、timeout、cancel、相同命令重放和整轮结果重放均持久化；
Bootstrap 只能创建独立 Approval handoff，Agent catalog 永远不包含审批决定。
`SUBMIT_PROJECT_EVIDENCE`、`SUBMIT_SOURCE_DISCOVERY` 与 `SUBMIT_RUNTIME_EVIDENCE` 也只创建各自的 R2 Approval
handoff；完成态证据 Job 可由 `SUBMIT_ADAPT` 通过严格 Job ID 绑定，但模型不能扩大 scan root/layers、伪造
artifact 或把 metadata/source evidence 当成 runtime evidence。
`PROVISION_HOST` 当前故意不进入 Agent catalog：它需要调用方显式选择两把 distinct forced-command 公钥，
而 catalog 声明 `model_generated_identity_available=false` 且模型不能读取 Controller 文件。CLI、认证 API 与 GUI
可以创建该 Job，通用 `RUN_JOB` 只能在独立 Approval 已持久批准后执行。若后续允许 Codex 发起主机置备，必须先
增加 Controller-owned key-set registry，让模型只能选择经过授权的 opaque key-set ref，不能提交 key/path。
每个 Session command 与整轮 turn 还分别持有跨 Controller 进程 guard；取消写入不等待长执行锁，并通过
持久 cancellation source 传播到正在运行的 Job。完成回执提交时会保留并发取消标记，避免最后写入覆盖取消。

`agent_runtime.py` 不再要求模型先给出 `SessionAgentPlan/Intent`，而是让 Codex 在每个安全回执后自主选择下一个
有限命令、提问或结束。Codex 运行于空白临时 workspace、`read-only` sandbox、ephemeral/ignore-user-config/
ignore-rules 模式；shell environment 不继承 Controller 环境，只注入独立 provider API key，Controller token、
SSH credential、canonical `robotctl` 和目标原始输出不进入模型上下文。provider 失败、输出不符合 schema 或超时
都会停止，不继续猜测动作。

当前入口包括 authenticated `/v1/session-agent/*` broker API、同步 `/v1/session-agent/turns`、
`robotctl target agent run`，以及独立 `rolo-deployment-control` 的 Natural-language deployment 面板；原
`rolo-vis` 仍为 read-only。GUI 冻结当前 target allowlist，token 只用于浏览器到 Controller 认证，不转交 Codex。
定向后端契约、API、CLI、配置测试及前端契约、类型检查、production build 已通过。

W9 尚不能标记完成：仍需真实 provider opt-in acceptance、专用 OS user/container 级只读范围验证，以及
prompt-injection/模型回归 eval 集。跨 Controller 多进程 command/turn guard 与活跃 Job 取消传播已进入当前切片，
但 HA 文件系统语义和 Controller 崩溃恢复仍需 W10 真机验证。这些项目完成后再删除或归档旧的严格意图原型；当前两份
实现并存仅用于迁移审计，旧原型未导出、未接路由，也不计入功能完成度。

### W10：真机、多架构与生产硬化

状态：`IN_PROGRESS_AUTOMATED_EVIDENCE_CONTRACT（静态 readiness、三阶段真实 SSH smoke、secret-closed receipt 和真机矩阵已建立；外部门禁未验收）`

依赖：W2-W9

覆盖：

- Ubuntu/Debian x86_64；
- Ubuntu/Debian ARM64；
- 无外网目标；
- 非 root 目标；
- sudo 需要交互审批；
- SSH jump host；
- host key rotation；
- 网络抖动/断线；
- 磁盘不足；
- 中途重启；
- ROS 与非 ROS workspace；
- PR #17 真实 editable LeRobot CLI 经 SSH 目标 sandbox 执行 `describe`/`--help`；
- Operation-scoped PATH 不包含未选中 CLI；
- virtualenv interpreter symlink/version-manager alias；
- editable `.pth` 指向 HOME、祖先目录或无工程 marker 时拒绝挂载；
- ML address-space/process budget 不足和调整；
- 多目标并行和单目标互斥；
- upgrade/rollback/enrollment rotation。

交付物：

- 真机验收矩阵；
- E2E SSH server fixture；
- chaos/failure-injection tests；
- installer SBOM 和签名验证；
- 安全评审和操作手册；
- RC rollout 与 rollback runbook。

当前切片新增 `SessionAgentProductionReadinessReport/v1`、`robotctl target agent readiness` 和 authenticated
`GET /v1/session-agent/readiness`。报告只对 feature flag、独立 provider credential 是否存在、HTTPS endpoint、
Codex executable 可解析性和 containment argv 契约给出本机静态结论；不输出 key、endpoint、可执行文件路径或
Controller 路径。dedicated OS isolation、真实 provider、真实 SSH prompt injection、多 worker 故障注入和 Linux
x86_64/ARM64 均固定为 `NOT_VERIFIED`，当前没有客户端自报通过的字段。当前还新增三阶段身份 opt-in 真实 sshd fixture、
两个独立 Controller 进程对相同 session command 的单 receipt replay 测试，以及同主机 lock owner 硬退出后的
立即回收测试；这只关闭本机软件恢复路径，不验证共享文件系统/多主机 HA。逐项证据要求记录在
`W10_ACCEPTANCE_MATRIX_ZH.md`；`test_real_session_agent.py` 只作为 provider bounded-schema smoke，
`test_real_ssh_target.py` 在未提供真实环境时必须 skip，两者都不能扩大为部署或生产验收结论。

当前切片进一步新增 `W10RealSshAcceptanceRequest/Receipt`、`W10TestReportSummary` 和
`robotctl target acceptance real-ssh`：产品入口分别以 provisioning、bootstrap、runtime credential purpose
执行固定 typed inspection/capability protocol，并绑定 OS image、package manifest、suite、target/connection、endpoint、
known_hosts、host-key pin、三阶段 identity、JUnit 汇总与 request/result digest。runtime identity 还调用既有只读
bootstrap `STATUS`，将目标验证后的 current index 投影为无路径的 package ID/version/manifest，并与声明值核对；
因此 package digest 不再只是操作者自报。JUnit 至少实际执行四个真实 SSH 用例，
全 skip/failure/error、DTD/entity 或摘要错配均失败。receipt 不落 host、credential reference、路径、用例名称、
stdout/stderr 或密钥；自动探测通过只产生 `automated_result=PASSED`，其 `matrix_status=NOT_VERIFIED`、
`manual_review_required=true`、`production_ready=false` 均不可由 CLI 参数提升。该能力关闭的是证据格式和采集入口，
不是 x86_64/AArch64、真实 sshd 或故障注入门禁；当前开发环境没有真实目标报告，矩阵状态保持不变。

同时新增手动 `w10-real-ssh-acceptance.yml`：只在受 Environment 审批的固定架构 self-hosted runner 上执行，
使用预配置三阶段身份并把 JUnit/receipt 留在 runner-local `ROLO_W10_EVIDENCE_DIR`。工作流不自动把可能含目标错误
文本的报告上传 GitHub Artifact；集中归档仍需独立批准数据目的地、保留期和脱敏策略。

installer SBOM 软件门禁也已进入当前切片：`TargetPackageSbom` canonical schema、确定性 builder、签名文件集和
installer 语义校验均有自动测试。缺失 SBOM、非 canonical 路径、额外/遗漏文件组件或 metadata 漂移都会失败
关闭；这证明 package contract，不替代真实 x86_64/AArch64 RC 的 SBOM/签名验收报告。

`RC_ROLLOUT_ROLLBACK_RUNBOOK_ZH.md` 已建立分架构 canary/扩批、停止条件、四眼审批和 evidence layout 草案。
当前切片进一步接入 strict target-runtime rollback Submission/JobSpec/Artifact、独立 R3 Approval、target registration
与 release-key pin 冻结、current/previous 双 CAS、统一 Job Runner、authenticated CLI/API/独立 GUI、
`SUBMIT_RUNTIME_ROLLBACK` broker action 和有界交互式 TUI 提交；派发后结果未知会进入 reconciliation，不会自动重试。
Approval scope 绑定实际 unsigned rollback request digest，Controller 用独立 Ed25519 私钥签发短时 proof；目标已安装
runtime 在读取 previous package 或改动 current 前用 target-local authorization pin 校验 proof。缺失/过期/错配 proof
及 signer 公私钥不匹配均失败关闭，runtime forced credential 仍只读。runbook 保持 `DRAFT_IN_PROGRESS`；剩余
blocker 是外部安全评审和真实 x86_64/AArch64 upgrade/rollback/断线/重启证据，而不是允许 raw SSH 或编辑 target
index 绕过控制面。

估算：`5-8 人周`

## 8. 分阶段发布

### Phase A：安全 SSH CLI Prototype

范围：W0-W2 的最小实现、现有 HMAC 兼容、CLI only。

用途：验证一个会话 Agent 通过 typed SSH tools 完成 inspect 和现有 Collector 调用。

限制：不宣称完成生产自主 bootstrap。

估算：`8-12 人周`

### Phase B：Linux 单用户产品 MVP

范围：W0-W7、Enrollment v4、target-side release describe/activation、CLI/TUI、
Job/Event/Approval、x86_64/ARM64 基线。

成功结果：用户无需手工执行 Collector 命令，可以从控制器完成 SSH 部署、注册、只读证据采集
和 Adapt。

估算：`34-50 人周`

### Phase C：统一交互产品

范围：W8-W9，扩展 GUI 和自然语言 Session Agent。

估算：在 Phase B 之上增加 `8-13 人周`；不能复用 rolo-vis 时增加更多前端投入。

### Phase D：生产 Fleet

范围：W10，并补充 RBAC、SSH CA、企业秘密管理、集中审计、多用户和 fleet rollout。

累计估算：`60-90 人周`

## 9. 推荐团队与日历

最低有效配置：

| 角色 | 主要负责 |
|---|---|
| Backend/Platform | Target Executor、Bootstrap、Packaging、Enrollment |
| Control Plane | Command、Job、Event、API、Audit |
| Product/UI | TUI、rolo-vis、Approval UX |
| Agent/Safety（可兼职） | Tool contract、自然语言、安全测试 |

日历估算：

- 1 名熟悉当前代码的工程师：MVP `8-11 个月`；
- 3 名工程师：MVP `3.5-5 个月`；
- 4-6 人团队：生产化 `4-6 个月`。

估算包含自动化测试和文档，不包含外部安全认证、特定厂商机器人集成或大规模现场试点。

## 10. 迁移与兼容

- 保留 `robotctl adapt start --evidence-mode local|remote` 至少一个兼容周期；
- 保留 `target-evidence collector-init/configure/collect` 作为专家和恢复入口；
- 新 `rolo target ...` 命令内部走 Command Bus；
- v1-v3 deployment/bundle 只读兼容，新自主部署默认 v4；
- 已固定的 HMAC deployment 不自动转为 Ed25519；必须显式 migration/rotation；
- 当前 artifact、Registry、Contract、Gate 和 release digest 不因 UI 来源变化；
- PR #17 的 `AdapterRuntimeContext.PATH`、`PYTHONPATH`、资源预算和 sandbox ABI 保持单一权威；
- Location/attestation 通过新版本 Schema 扩展，不回退为继承控制器 PATH；
- read-only Web API 保持兼容，新增写 API 使用独立 versioned models；
- `TARGET_DEVICE_OPERATION_MANUAL_ZH.md` 保留手工严格置备，新增 Agent-assisted 章节。

## 11. 测试策略

### 11.1 单元与属性测试

- Schema strict validation；
- Command canonicalization/digest；
- path、argv、host、port 和 proxy validation；
- secret redaction；
- enrollment signature/replay/rotation；
- LocatedRuntimeContext location/provenance 和 target-path controller rejection；
- target describe attestation identity/digest/freshness；
- Job state transition 和 idempotency；
- approval digest/expiry/principal binding。

### 11.2 Executor conformance

同一 fixture 对 Local/SSH Executor 验证：

- stdout/stderr/exit/timeout；
- cancel/process-tree cleanup；
- file transfer digest；
- host-key policy；
- unavailable dependency；
- bounded output；
- no shell interpolation。

### 11.3 Integration

- 容器或 VM 中真实 `sshd`，不得只 monkeypatch `subprocess.run`；
- bootstrap/install/upgrade/rollback；
- target enrollment 和 fresh bundle；
- controller Adapt Journey；
- API -> Job -> SSH -> target -> evidence -> Gate；
- frozen Bundle -> SSH target -> PR #17 sandbox describe -> signed attestation -> Controller Gate；
- 同一 LeRobot/virtualenv fixture 的 Local 与 SSH runtime-context parity；
- SSE reconnect 和 restart recovery。

### 11.4 真机验收

自动化工程测试不能代替：

- 真实 ARM64 目标；
- 真实 ROS graph；
- 非 ROS Application/CLI；
- 网络中断和目标重启；
- 操作系统权限差异；
- 目标主机替换、host key rotation 和 enrollment rotation。

## 12. 风险与控制

| 风险 | 控制 |
|---|---|
| Agent 获得无限 SSH 权限 | typed tools、credential isolation、approval、raw shell 默认关闭 |
| 同信道 bootstrap 削弱独立信任 | SSH CA/指纹确认、Ed25519 enrollment、可选物理确认 |
| GUI/TUI/CLI 行为漂移 | 单一 Command Bus 和 Command digest conformance |
| 长任务中断留下半安装 | staged activation、checkpoint、idempotency、rollback |
| 目标输出 prompt injection | 标记 untrusted、结构化解析、不给输出定义 policy 的能力 |
| ARM64/离线部署失败 | 预构建制品、manifest、离线上传、架构 CI |
| 控制器错误验证目标绝对路径 | LocatedRuntimeContext、目标侧存在性/digest 验证、attestation |
| Local 与 SSH sandbox 行为漂移 | 复用同一 launcher/runner contract 和 cross-executor conformance |
| 远程部署用 `invoke` 冒烟产生副作用 | Promotion/Bootstrap 只允许 describe/help，invoke 仅走授权 Runtime |
| ML CLI 资源预算不足或被无限放大 | 继承 PR #17 有界配置、preflight blocker、目标策略上限 |
| Job 状态与 artifact 不一致 | atomic index、final integrity validation、恢复审计 |
| 远程源码和本地副本混淆 | TargetWorkspaceRef、目标 manifest、provenance |
| 产品范围失控 | Phase gate、MVP 非目标、每阶段独立验收 |

## 13. Phase Gate

### Gate A：允许进入 Bootstrap 实现

- W0 ADR 和威胁模型通过评审；
- TargetProfile/Command Schema 冻结 v1；
- credential 和 host-key policy 明确；
- raw shell 默认策略明确。

### Gate B：允许进入 GUI/Natural Language

- CLI 经真实 SSH E2E 完成 bootstrap/enroll/collect/adapt；
- Job 可恢复且审批绑定 digest；
- Local/SSH Executor conformance 通过；
- secret redaction 测试通过；
- Enrollment v4 replay/rotation 测试通过；
- 目标侧 describe attestation 与 Local PR #17 sandbox parity 测试通过；
- Promotion/Bootstrap 不执行 invoke 的回归测试通过。

### Gate C：允许生产 RC

- x86_64/ARM64 真机矩阵通过；
- upgrade/rollback/断线/重启测试通过；
- 安全评审无 P0/P1 未解决问题；
- GUI/TUI/CLI/NL 等价命令测试通过；
- 手册、恢复流程和 rollback runbook 完成。

## 14. 前四周建议 Backlog

### Week 1

- 完成 W0 ADR 和 threat model；
- 确定 v4 签名库和目标包形式；
- 建立 TargetProfile、DeploymentCommand Schema；
- 建立真实 `sshd` CI fixture 技术验证；
- 固定 PR #17 Runtime Context/Sandbox baseline fixture 和 digest 语义。

### Week 2

- 实现 Command Bus skeleton；
- 实现 credential reference/redaction；
- 实现 LocalTargetExecutor contract；
- 让现有本地 `adapt start` 走兼容 Command path。

### Week 3

- 实现 SshTargetExecutor read-only inspect；
- 加入 strict/confirmed host-key assessment；
- 建立 Local/SSH conformance suite；
- 输出 canonical CLI。

### Week 4

- 实现 bootstrap dry-run 和 typed step model；
- 加入 Job/Event 最小持久化；
- 通过真实 SSH 完成 `inspect -> existing collector collect`；
- 完成 frozen demo Bundle 的目标侧 sandbox `describe` spike，不执行 `invoke`；
- 评审 Phase A 数据，再决定进入 package installer 或先修正契约。

## 15. 完成定义

本计划完成不是指“Agent 能 SSH 登录”，而是以下条件全部成立：

- 用户通过 CLI、TUI、GUI 或自然语言均可创建统一的目标任务；
- 一个会话 Agent 可以自主推进读取和低风险步骤；
- 所有状态变更都有结构化工具、审批、Job、Event 和 Audit；
- 目标机 enrollment 自动且目标本地执行；
- 目标私钥不离开目标，控制器可验证证据；
- SSH bootstrap、升级和回滚幂等可恢复；
- Local/SSH 两种拓扑共享 Adapt/Gate 权威；
- SSH 模式的目标 CLI、virtualenv、editable source 和解释器仅在目标侧 production sandbox
  验证和运行；
- Promotion 与部署验收从不调用 `invoke`；
- Adapter Agent 无部署凭据；
- 真机、多架构和故障矩阵通过；
- 当前 CLI、evidence 和 artifact 兼容策略有测试保护；
- 发布说明明确哪些结论只是软件验证，哪些已经完成真机验收。
