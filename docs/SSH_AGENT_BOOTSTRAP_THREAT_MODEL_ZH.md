# SSH Agent Bootstrap 威胁模型

状态：`W5_CONTRACT_BASELINE`

基线：`main@666f35c`

## 1. 范围

本模型覆盖 Session Agent 从控制器通过 SSH 检查、安装、enroll、采集证据、部署 frozen
Adapter Bundle 并触发目标侧 `describe` 的路径。

不覆盖机器人运动安全证明、目标物理防拆、企业 IAM 具体实现或外部 SSH CA 运维。

## 2. 资产

- bootstrap/runtime SSH credential；
- SSH host key/CA trust；
- Collector private key/public descriptor；
- Collector v4 configuration、challenge attestation、controller public-key pin 和 rotation transition；
- TargetProfile、ConnectionProfile 和审批记录；
- signed target bundle 和 installer；
- target workspace、CLI、virtualenv 和 editable source；
- target evidence bundle；
- frozen Adapter Bundle、Runtime Context 和 release；
- Job/Event/Audit；
- Tool Catalog、Policy 和 authorization capability。

## 3. 信任边界

```text
User
  | approval
Session Agent (untrusted planner output)
  | typed tool request
Command/Policy/Approval boundary
  | credential reference
Local/SSH Executor
  | pinned SSH transport
rolo-target companion
  | target filesystem and sandbox
Adapter target route
```

目标机返回的 banner、stdout、stderr、README、help 和 Wiki 都属于不可信输入，不能修改 Policy
或批准权限。

## 4. 安全不变量

1. Agent prompt、普通 artifact 和浏览器响应不包含 credential material。
2. `STRICT` SSH 连接没有 fingerprint/CA 时失败关闭。
3. host key 变化不自动接受。
4. bootstrap credential 不传给 Adapter Agent 或普通 Runtime。
5. Collector private key 不离开目标。
6. 控制器不验证或挂载目标绝对路径。
7. 目标侧只运行 digest-bound、versioned typed command。
8. Promotion、bootstrap 和 deployment smoke 不执行 `invoke`。
9. 首次目标未安装 `robotctl` 时，bootstrap credential 只允许产品内置的 `python3 -` capability script 和固定
   preinstall transfer handler；OpenSSH 虽经目标 login shell 启动固定命令，但 Agent、profile、
   manifest、路径和分块数据都不得进入 remote command 字符串。
10. transfer 目标固定为目标账号的 Rolo incoming root；请求只包含规范化相对路径、manifest/file/
    chunk digest、offset 和有界 Base64 数据，不提供任意远端路径。
11. 上传完成不等于安装或激活；执行安装前必须再次验证 package exact file set、manifest、签名、
    pinned release key 和 preflight，失败不得改变 current index。
12. 安装完成后的 runtime credential 必须由 OpenSSH forced command 限制到已安装的 dispatcher；
    dispatcher 只接受精确的 inspect 或 bootstrap STATUS/HEALTH，禁止 `python3 -`、安装、激活、
    回滚、交互 Shell、PTY 和 forwarding。
13. release activation 必须发生在 Controller Gate 通过之后。
14. 取消或网络中断后，未知远端状态必须标记 `BLOCKED/REQUIRES_RECONCILIATION`，不能报告成功。
15. Collector v4 private key 只能在目标 identity store 中生成和使用；controller 只接收由 challenge
    绑定的 descriptor/configuration/public key，任何结果、事件或普通日志不得包含 private-key path。
16. v4 rotation 必须同时满足 expected old collector CAS 和旧 key 对 new descriptor 的 transition
    签名；新 key 自签或只有 SSH host key 不能授权替换 controller pin。
17. evidence-v4 虽为 READ_ONLY，仍可能包含敏感主机信息；在 scoped authorization capability 能绑定
    principal、target、layers、destination 和 expiry 之前，不加入 runtime SSH forced-command allowlist。
18. 控制器只能把远端 workspace/runtime path 当作目标观察值做语法、identity 和 digest 校验；不得对
    这些路径调用控制器本机 `Path.exists()`，也不得用同名本地 checkout 替代目标 manifest。
19. 目标 workspace manifest 只覆盖显式选择的普通文件，拒绝 parent traversal、symlink、非普通文件和
    size/count 超限；观察时间不得影响同一 snapshot 的 content digest。
20. 目标 `describe` stdout 必须进入 secret-closed 结构化模型；attestation 绑定 request nonce、release、
    Bundle、Runtime Context、sandbox profile、完整输出摘要和 operation mapping，且该路径不得执行 `invoke`。
21. Adapter release 上传或暂存不等于激活；目标 staged 目录必须由 release identity 与摘要推导，验签、
    exact file set、逐文件 digest 或 Runtime Context 任一失败都不得写入 `current.json`。
22. Controller 只能在验证 Collector `describe` attestation 后签发短时效 PASSED Gate 收据；收据必须绑定
    target/robot/collector、release、transfer、Bundle、Runtime Context、sandbox、request 和 output digest。
23. 激活必须重新验证 Gate 收据与 staged transfer，并以锁和原子 current index 完成；回滚必须携带
    expected-current digest 做 CAS，冲突或中断不得静默覆盖现有 current。
24. Adapter release stage、describe、activate/rollback、project-evidence、source-discovery、runtime evidence 和 target runtime rollback 必须携带目标
    可验证的短时 authorization proof。runtime forced credential 只新增固定的只读 `project-evidence`、
    `source-discovery` 与 `evidence-v4` 入口；其余
    命令仍拒绝。target runtime rollback 通过
    bootstrap credential 的固定 `target-executor bootstrap` 命令进入已安装 runtime，也必须先通过 proof 校验，
    不能凭 SSH 身份或裸 `approval_id` 获权。
25. authorization proof 必须绑定去除 proof 后的完整 typed request 摘要及精确 Approval scope；目标只信任本地
    authorization-key pin，不接受请求自带 authorization key。Bootstrap transaction 支持 pin 首次安装和 CAS
    轮换；Controller 私钥不得传给目标。没有真实主机安装、轮换、过期与断线证据时仍不得宣称生产信任闭环完成。
26. 远端项目证据探测只接受显式、排序、数量受限的相对候选文件；不得接受 glob、递归 inventory 或目标
    输出建议的新路径，未声明文件不得进入 manifest；它需要 `READ_PROJECT_EVIDENCE` scoped proof，且只能通过
    runtime forced credential 的固定 typed command 进入。Controller SSH 凭据只负责派发，目标必须使用本地
    authorization-key pin 复核 proof、完整无 proof 请求摘要、Approval scope、target 和 expiry 后才可读取文件。
26a. 远端源码分析必须使用独立 `ANALYZE_PROJECT_SOURCE` Approval，并把 registration、workspace、精确 scan roots、
    文件/字节/超时预算和完整 request digest 写入 proof。目标拒绝绝对路径、parent traversal、symlink workspace/root
    和边界逃逸；只返回严格结构化依赖、入口点、ROS interface/name、语义候选、相对路径与摘要，不返回源码、文档/
    launch 正文、原始诊断、绝对路径或目标建议命令。Controller 在 Adapt 前和 Runner 内都要重新验证不可变 artifact、
    target/registration/workspace/request/summary digest 与 freshness。
26b. 远端运行时证据必须使用独立 `COLLECT_RUNTIME_EVIDENCE` R2 Approval，精确绑定 target registration、当前
    collector descriptor/config/key pin、固定 `hw/linux/ros` layers、nonce、issued/expires 和完整 unsigned request
    digest；有效窗口最长 5 分钟。runtime forced credential 只能把结构化请求交给固定 `evidence-v4` dispatcher，目标
    先用本地 authorization pin 验证 proof，再由 enrolled collector 签名 bundle。Adapt submission 与 Runner 必须分别
    使用当前 collector pin 重验 signature、request、target、registration、collector 和 payload/freshness；禁止把旧
    bundle、metadata/source artifact 或 SSH 身份本身解释为运行时证据授权。
27. release reconciliation 必须是只读的 Controller 计划：目标状态重新验签 current/previous/desired stage，
    Controller 将其与权威 release index 比较并生成 CAS 输入；状态不可验证时必须保留 unknown/blocked，
    不能自动重复 stage、activate 或 rollback。
28. Job event 必须先作为 hash-chain append-only record fsync，并携带恢复 snapshot；原子 Job snapshot 落后
    journal 时只能从已验证链重放，链断裂、摘要篡改或 snapshot 指针超前必须失败关闭。
29. Approval request 与 decision 必须分离且不可原地改状态；decision 绑定独立 approver principal、request
    digest、job、target、command digest、action 和 expiry，请求人不得批准自己的请求。
30. cancel 或 controller restart 后只要远端副作用状态未知，Job 必须进入
    `BLOCKED/REQUIRES_RECONCILIATION`；retry/resume 不得绕过该 disposition。
31. Approval 必须在签发 capability 前绑定精确 `authorization_scope_sha256`；同 target/action 下的另一份
    payload 也不得复用原 Approval。grant 最长 10 分钟，并同时绑定 Approval decision、command 和 approver。
31. 同一 target 的冲突部署必须持有跨进程 lease；idempotency key 相同但 command digest 不同必须拒绝。
32. Session Agent 不得接收 Controller bearer、SSH credential 或 `approval:write`；模型命令不得包含 principal、
    requested-by、idempotency key、shell 或 argv，这些字段只能由 authenticated broker 绑定。
33. 自主编排每次只执行一个 catalog command 并持久化一个 receipt；创建 Job 与运行 Job 不得通过
    `run_after_submit` 合并，以便 action budget、审计和失败边界逐步生效。
34. Session Agent target allowlist 必须由 GUI/CLI/API 调用方在会话开始前冻结；模型不能扩大 target scope，
    也不能通过 Job/Approval ID 间接读取 allowlist 外目标。
35. Codex 只能收到 secret-closed projection；canonical `robotctl`、target banner、README、日志、stdout/stderr
    和异常正文不得重新进入模型 history。canonical CLI 只回给用户和审计面。
36. Session Agent 整轮 idempotency 必须同时绑定 message、target allowlist、budget 和 timeout；同 key 重试返回
    已持久化结果，不重新调用模型，不同请求使用同 key 必须冲突。
37. Codex provider 必须使用 dedicated API key、空白临时 HOME/CODEX_HOME、read-only/ephemeral sandbox、忽略
    user config/rules，且 shell environment 不继承 Controller 环境；未配置时失败关闭。
38. Session command 与整轮 turn 必须分别跨 Controller 进程串行；取消不得等待长执行锁，必须先持久化，再由
    进程内事件或持久 cancellation source 传播到活跃 Job。最终 receipt 写入必须合并而不是覆盖并发取消状态。
39. 生产 readiness 不得由客户端布尔值、自然语言或本机静态自检签发。真实 provider、OS isolation、SSH
    prompt injection、HA failure injection 和每个 CPU 架构必须保持独立外部门禁；无环境绑定证据即
    `NOT_VERIFIED`，且报告不得返回 provider key、endpoint、executable path 或 Controller path。
40. 文件 guard 必须记录 owner host、PID 和创建时间。同主机 owner 已确定死亡时可以立即回收；跨主机 owner
    只能按有界 stale policy 回收。PID 状态未知、owner 无法可信解析或权限不足时必须失败关闭，不能把“无法确认
    存活”当成“已经死亡”。
41. 每个可安装 Target package 必须包含固定路径的 CycloneDX 1.6 SBOM。SBOM 文件的 size/digest/role 必须进入
    Ed25519 签名 manifest；installer 还必须把 SBOM application/file component 重新投影并与 package id、版本、
    架构、Python 约束及所有非 SBOM 文件的 path/hash/role/mode/size 精确比对，不能只验证 JSON 语法或文件摘要。
42. 自动 Collector 配置请求只允许注册 workspace root、有限的规范化相对 executable 候选和 ROS 自动选择开关；
    文件解析、symlink/边界/类型/大小检查与 digest 计算必须发生在目标侧。Controller 不得替目标声明本地存在性，
    enrollment attestation 必须绑定目标实际解析出的完整 configuration digest。
43. 首次主机置备必须显式区分已有管理权限的 provisioning 连接、签名包事务专用 bootstrap forced-command
    连接与最终最小权限 runtime forced-command 连接；账号、credential、HOME 或 install root 不得因复用
    单一身份而隐式切换。固定 launcher 必须解析并复核已激活的 digest-bound runtime，不能把模板中的静态
    路径当成安装完成证据。
44. bootstrap authorized key 只能进入固定 dispatcher；dispatcher 的 original-command allowlist 只有 runtime
    capability、package transfer 和 bootstrap transaction，未知命令不得回显。稳定 runtime launcher 每次转发前
    必须重新校验 active index、manifest identity/digest、contained non-symlink entrypoint、size/mode/digest。
45. HostProvisioningPlan 必须完整列出每个 sudo argv 或文件 effect（path、owner、group、mode、content digest），
    绑定三阶段 registration 和两把不同的 forced-command 公钥。只读 plan、模板生成或 schema 测试不构成主机
    mutation 已执行；apply 必须另走持久 Job/Approval，runtime 激活前不得启动 systemd service。
46. Host provisioning apply 必须冻结为 `PROVISION_HOST` Job，Approval 的 authorization scope 必须等于完整
    Job spec digest，并在执行前重新核对 target registration、approver principal、expiry 与 `USE_SUDO` action。
    计划只能从 stdin 进入固定 root installer，不能拼入 SSH remote command。
47. 固定 root installer 必须先验证 euid、schema、target/user/template version、固定路径、完整 step set、sudo
    scope、content digest 与 expected-current CAS；落盘使用安全父目录检查和原子 replace。相同计划返回
    `ALREADY_CURRENT`；已有不同计划但无正确 CAS 时失败关闭。
48. Controller 只能使用 `SSH_PROVISIONING` 身份执行 host apply。命令启动后传输失败属于未知远端结果，Job
    必须写入 artifact 并进入 `REQUIRES_RECONCILIATION`，不能盲目自动重放 sudo transaction。
49. 首版 Session Agent 不接收 host provisioning 公钥、私钥路径或 credential reference，也不能生成目标身份。
    主机置备由认证 CLI/API/GUI 调用方显式提供两把公钥并交由独立审批；未来若开放给自然语言入口，必须先引入
    Controller-owned key registry，只允许 Agent 选择 opaque key-set ref。
50. 未知 host apply 只能通过独立 `RECONCILE_HOST` Job 处理。observer 使用 `SSH_PROVISIONING` 身份、固定
    sudo 脚本和冻结计划 stdin，R2 Approval scope 等于完整 reconcile spec；不得执行 installer 或任意 shell。
    只有 commit marker 与全部受管对象精确匹配时才能把原 UNKNOWN checkpoint 标为 COMPLETE；确认未提交只允许
    新 attempt，different/drift 必须继续阻断。observation artifact、原 Job event 和 reconcile Job checkpoint 必须
    digest-bound 且支持控制器崩溃恢复，避免重复观测被误解释为重复写入。
51. Host rollback 不能解释为删除 runtime 用户、清空 `/var/lib/rolo` 或执行调用方 shell。它只能引用两个
    同目标、已完成的 host configuration Job，用旧 Job 的 forced-command 公钥和当前 registration 重建 canonical
    plan，并把当前 Job plan digest 作为 CAS。审批必须是 R3 `ROLLBACK_HOST_CONFIGURATION` 且 scope 绑定完整
    spec；目标仍只执行固定 installer。任一 Job 非完成态、跨 target、registration 漂移或 commit marker CAS 不符
    都必须失败关闭。
52. Host provisioning 只 enable systemd unit；runtime Bootstrap 成功后首次启动必须另走
    `START_TARGET_SERVICE` R2 Job。spec 必须同时绑定已完成 host configuration Job、Bootstrap Job、当前
    registration、host plan digest、active runtime manifest digest 和固定 unit name。目标只接受固定 sudo
    START/STATUS 协议；不得把 unit、argv 或 shell 交给模型自由生成。
53. service start 传输结果未知时不能按 systemctl 幂等性自动重放。独立 `RECONCILE_TARGET_SERVICE` R2 Job
    只能发 STATUS：ACTIVE 闭合原 UNKNOWN checkpoint，INACTIVE 只允许新 attempt，host/runtime 摘要不符保持
    `REMOTE_STATE_DIVERGED`；连接/协议失败不改变原 Job。reconcile artifact 与原 Job event 必须 digest-bound
    且支持控制器崩溃恢复。
42. SSH Adapt 不得把目标绝对 workspace 转换为 Controller 本地路径。metadata-only Journey 必须绑定已完成且新鲜的
    project-evidence Job、artifact、command、registration、workspace 和 manifest digest；Runner 使用前重新加载验证。
    目标 observed paths 只能作为摘要绑定，不能成为 Controller source/build/install roots。篡改、过期、target 混用
    或 registration 漂移必须失败关闭。可选 source-discovery binding 必须与同一 project-evidence workspace digest
    一致，并使用独立 `TARGET_SOURCE` 低置信度层级；远端相对路径不得触发 Controller 文件读取。metadata/source
    `DISCOVERY_COMPLETE` 都不得解释为 runtime probe、Adapter release 或 Gate 已完成。`runtime-readonly` Journey 必须
    额外绑定 26b 的完成态 runtime evidence artifact，并只消费重新验签产生的 `ProbeResult`；不得在 Adapt 内部另发
    未审批的临时采集请求。

## 5. 威胁与控制

| 威胁 | 影响 | 控制 |
|---|---|---|
| SSH MITM | 假目标、窃取 bootstrap 内容 | STRICT pin/SSH CA、CONFIRMED 带外确认、TOFU_DEV 默认关闭 |
| Agent 泄漏私钥 | 目标完全失陷 | credential reference、executor 持密、prompt/log redaction |
| Agent 生成任意 root shell | 主机被任意修改 | typed tools、版本化步骤、sudo 审批、raw SSH 默认关闭 |
| Agent 生成或替换 forced-command key | 锁定合法运维身份、植入攻击者密钥 | 首版 Agent 不暴露 host provisioning；CLI/API 显式公钥、distinct-key validation、plan digest、独立审批；后续仅 opaque key-set ref |
| runtime 密钥注入 stdin 脚本 | 绕过 typed protocol 执行任意代码 | forced command、精确 original-command allowlist、运行期禁止 `python3 -` |
| 恶意目标输出 prompt injection | Agent 越权或改变计划 | untrusted 标记、结构化解析、输出不能定义 policy/approval |
| 安装包篡改或无关 SBOM | 执行攻击代码、依赖/文件库存与实际制品不一致 | manifest signature、CycloneDX SBOM 进入签名文件集、SBOM/manifest 语义交叉验证、staged activation |
| 路径注入/参数拼接 | 任意命令执行 | argv-only executor、禁止 shell 拼接、路径 Schema 与边界检查 |
| symlink/path escape | 读取宿主秘密或扩大 mount | target-side resolve、scope validation、PR #17 sandbox rules |
| 控制器/目标路径混淆 | 错误 Gate 或运行错误文件 | LocatedRuntimeContext、target attestation、禁止 controller existence check |
| 远端项目递归枚举 | 泄漏未授权源码、密钥或大目录 | explicit candidate set、no glob/recursion、target-side bounds、`READ_PROJECT_EVIDENCE` proof、runtime key 禁止 |
| Collector bundle replay | 陈旧事实进入 Adapt | nonce、issued/expires、freshness、request binding |
| Collector identity replacement | 伪造证据 | public-key pin、old-key rotation transition、显式 re-enroll approval |
| enrollment challenge replay | 复用旧 descriptor 或冒充持钥方 | request digest、nonce、issued/expires、proof-of-possession |
| enrollment 中断/并发 | 半注册或多个 active key | generation directory、跨进程锁、原子 current、collector CAS |
| v4 bundle 篡改或错配 | 错误目标事实进入 Adapt | descriptor/config/key pin、request binding、payload digest、Ed25519 verify |
| 只读证据权限扩大 | runtime key 导出敏感环境信息 | forced-command 只接受携带 `COLLECT_RUNTIME_EVIDENCE` proof 的固定 evidence-v4 请求；固定 layers、collector pin、5 分钟窗口、目标本地验权与 Controller 二次验签 |
| `describe` 输出伪造 | 错误 Bundle 通过 Gate | target/release/runtime/sandbox digest-bound attestation |
| staged release 被替换或越权激活 | 未经 Gate 的代码成为 current | signed exact transfer、derived stage path、short-lived Gate receipt、activation reverify |
| 请求内 release key 或 rollback payload 被替换 | 攻击者使用自选 key 或篡改 CAS 回滚错误版本 | release key/完整 typed request 纳入 exact Approval scope；短时 proof 由 target-local auth pin 验证；真实 Bootstrap/轮换验收前不宣称生产闭环 |
| 并发激活/错误回滚 | current 丢失或回到错误版本 | per-target lock、atomic current index、expected-current CAS |
| 用 `invoke` 做冒烟测试 | 摄像头、写文件或运动副作用 | Promotion/Bootstrap invoke prohibition、测试保护 |
| Local/SSH sandbox 漂移 | 远端执行边界弱于本地 | 同一 launcher ABI、cross-executor conformance |
| ML 资源无限扩张 | DoS | PR #17 bounded budget、target policy ceiling、timeout/cancel |
| Job 重放 | 重复安装/激活 | idempotency key、command digest、step checkpoint |
| Event journal 篡改或 snapshot 回退 | UI/Agent 看到伪造进度并重放步骤 | hash chain、fsync-before-snapshot、recovery snapshot replay、pointer verification |
| Agent 自批或替换审批主体 | 越权执行 R3 写操作 | separate immutable decision、requester/approver separation、principal+digest+expiry verify |
| Codex 直接调用原始 `robotctl` 或修改 store | 绕过领域 policy、伪造 Job/Approval | 模型不获得原始 CLI/PATH/store；只输出单步 command，由进程外 authenticated broker 执行 |
| Controller token/SSH key 进入 Codex 子进程 | prompt/shell 外泄控制面或目标凭据 | dedicated provider key、最小环境、shell inherit=none、空白 HOME、Controller/SSH credential 不传入 |
| 自然语言扩大 target 或权限 | 横向读取/写入其他目标 | 会话前冻结 target allowlist、permission exact match、Job/Approval 间接引用再次校验 target |
| 整轮 HTTP 重试重复调用模型 | 重复 Job、副作用或不同总结 | open request digest、per-command sequence/digest replay、持久 turn result replay |
| 多 worker 重复执行或取消丢失 | 重复模型调用、重复 Job、取消后仍继续 | command/turn 跨进程 guard、独立原子取消写入、持久 cancellation source、receipt 合并提交 |
| Controller 硬退出遗留 guard | 同一 session 最长时间不可用，或错误抢占仍在运行的 worker | host+PID owner metadata、同主机存活检测、跨主机 stale policy、未知状态失败关闭、双进程 replay/硬退出测试 |
| 静态自检被当作生产验收 | 未经真机验证即开放自主部署 | secret-closed readiness 契约、外部门禁不可自报、逐平台矩阵、production-ready fail closed |
| 并发部署 | split-brain release | per-target lock、atomic index、reconciliation |
| 网络中断 | 半安装或状态未知 | staging、checkpoint、remote status query、no-success-on-unknown |
| reconciliation 误判并自动写入 | 覆盖正确 current 或回滚到错误版本 | verified digest-only snapshot、controller authority binding、plan-only output、CAS+approval |
| 日志泄漏 | secret/路径/data exposure | structured sanitized events、size limit、classification |

## 6. 审批矩阵

| 动作 | 默认审批 |
|---|---|
| 读取连接能力和系统版本 | 自动，审计 |
| 使用预置 STRICT host key 连接 | 自动，审计 |
| 首次确认 host fingerprint | 用户确认 |
| 安装目标 runtime | 用户确认 |
| 使用 sudo | 用户确认，显示规范化 argv/影响 |
| 安装/更新主机账号、dispatcher、launcher、authorized_keys、systemd | 独立 R3 `USE_SUDO` 确认，绑定完整 plan digest 与 CAS |
| 创建 Collector identity | 首次 bootstrap 计划内确认 |
| 替换 Collector identity | 单独确认并填写原因 |
| 升级/回滚 target runtime | 用户确认 |
| 激活新 Adapter release | Gate 通过后按策略确认 |
| raw SSH expert mode | 默认禁止；开启时逐次 R3 确认 |

Agent 不能批准自己的请求。Approval 必须绑定 principal、target、command digest、action 和 expiry。

## 7. 失败与恢复

- host-key mismatch：停止，不更新 pin；
- credential failure：停止，不回退密码交互；
- preflight 缺依赖：返回 blocker，不隐式修改系统；
- upload/verify failure：删除或隔离 staging，不影响 current；
- transfer interruption：查询目标已持久化 offset，从该 offset 续传；相同 chunk 重试不得重复追加，
  file digest 不一致时清除损坏 part，已完成 incoming package 仍不得自动激活；
- enrollment 中断：新 identity 不进入 controller pin；
- describe timeout/nonzero：Gate 失败，不调用 invoke；
- activation 中断：查询 target current digest，无法确认时进入 reconciliation；
- controller restart：从 append-only Event 和 target query 恢复，不重放已完成步骤。

## 8. 剩余风险

- 已经取得 root 的恶意目标可以伪造普通软件身份；Ed25519 Collector key 不是硬件 attestation；
- 首次 CONFIRMED/TOFU 信任质量取决于用户核验；
- SSH credential provider 和企业 CA 本身仍需独立安全评审；
- `describe` 由第三方依赖 import 时仍可能产生副作用，必须继续使用 sandbox、network policy、
  TMP redirect、timeout 和资源限制；
- 真机物理结果、安全和可靠性必须在 Diagnose/Verify 阶段另行验证。
- Session Agent 已有基于 Controller artifact 文件系统的跨进程 guard；双进程相同 command replay 和同主机 owner
  硬退出后的立即回收已有软件测试。共享文件系统/多主机锁语义、PID reuse、跨主机 stale policy 和远端 cancel
  confirmation 仍需 W10 HA 故障注入验证；
- read-only Codex sandbox 与空 HOME 已减少可见面，但专用 OS user/container 和实际平台 ACL 仍需 W10 真机验证；
- W10 自动化 receipt 即使全部探测通过也固定保持 `NOT_VERIFIED/production_ready=false`；它只保存目标、环境、
  三阶段身份和 typed request/result 的摘要绑定，不保存 host、credential reference、known_hosts 路径、原始输出或密钥，
  因而不能被当作人工安全复核或生产 acceptance signature；
- W10 JUnit 只提取计数、时长和文件摘要，拒绝 DTD/entity、全 skip 和失败报告；原始 JUnit 默认仅留在受保护
  self-hosted runner，不自动上传外部 artifact 存储，避免未经批准外发目标错误文本或路径；
- W10 package manifest 不能只依赖 workflow input；runtime credential 必须通过只读 bootstrap `STATUS` 获取目标校验过的
  current index，receipt 只投影 package ID/version/manifest 并拒绝声明漂移，不记录 install path；
- 模型 prompt-injection 行为需要持续 eval，不能仅凭 prompt 指令或结构化输出宣称完全隔离。

## 9. W1-W3 安全验收入口

后续实现至少增加：

- inline private key/password 被 Schema 拒绝；
- STRICT 无 pin/CA 被拒绝；
- host-key change 需要新 approval；
- Agent 工具结果中无 secret；
- argv 元字符不经过 shell；
- malicious banner/help 不能改变 Command/Approval；
- cancel/timeout 后不报告成功；
- Local/SSH Executor 对相同 contract 产生等价规范化结果。
- preinstall capability/transfer 的 SSH remote command 不含 request、路径或 chunk 数据；
- chunk/request/response digest 与 identity 不匹配时失败关闭；
- 上传中断后按 target-observed offset 恢复，完整重复上传为零新增字节；
- incoming 完整或损坏均不能绕过 installer 的签名、健康检查与原子 current 切换。
- runtime credential 只能进入已安装 dispatcher，STATUS/HEALTH 以外请求和未知 original command
  失败关闭且不回显原命令；
- systemd/authorized_keys 模板内容有 digest 绑定，输入拒绝控制字符、shell 元字符和非规范化路径。
- v4 challenge tamper/replay/expiry 和 robot/target/collector/host mismatch 失败关闭；
- 并发 enrollment 只有一个 generation 成为 current，中断写入不产生 active 半身份；
- rotation transition 由旧 key 验签后才更新 controller pin，旧 bundle 在新 pin 下失败；
- legacy HMAC bundle 保持只读兼容，不被静默迁移为 Ed25519。
